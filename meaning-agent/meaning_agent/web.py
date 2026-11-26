"""Localhost-only web UI and JSON API with a strict static-asset allowlist."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .catalog import resource_catalog
from .constants import DEFAULT_WEB_PORT, D7_MODULES, EVIDENCE_LEVELS, SCALES
from .engine import APPROVAL_STATES, analyze, review
from .i18n import bi
from .llm import LLMConfig
from .safety import MAX_BODY_BYTES, strict_json_loads, valid_local_host
from .skills.registry import registry_metadata

ASSET_DIR = Path(__file__).resolve().parent / "static"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class MeaningAgentServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def safe_api_error(category):
    messages = {
        "invalid_input": ("输入无效；请检查文本、上下文 JSON 与选项。", "Invalid input; check text, context JSON, and options."),
        "request_too_large": ("请求体过大。", "Request body is too large."),
        "forbidden": ("请求来源不被允许。", "Request origin is not allowed."),
        "not_found": ("资源不存在。", "Resource not found."),
        "method_not_allowed": ("请求方法不允许。", "Method not allowed."),
        "internal_error": ("内部错误；未返回敏感详情。", "Internal error; sensitive details were not returned."),
    }
    zh, en = messages.get(category, messages["internal_error"])
    error = {"code": category, "message": bi(zh, en)}
    return {**error, "error": error}


def _valid_origin(value, port):
    if not value:
        return True
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return False
        return parsed.hostname in ("127.0.0.1", "localhost", "::1") and (parsed.port or 80) == port
    except ValueError:
        return False


def _headers(handler, content_type, length, api=False):
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(length))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Frame-Options", "DENY")
    if api:
        policy = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    else:
        policy = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    handler.send_header("Content-Security-Policy", policy)


def _llm_configured():
    try:
        return LLMConfig.from_env() is not None
    except ValueError:
        return False


def create_server(port=DEFAULT_WEB_PORT, host="127.0.0.1"):
    if host != "127.0.0.1":
        raise ValueError("web UI must bind to 127.0.0.1")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    class Handler(BaseHTTPRequestHandler):
        server_version = "MeaningUI/1.0"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, format, *args):
            return

        def handle(self):
            try:
                super().handle()
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                return

        def version_string(self):
            return self.server_version

        def _send_bytes(self, status, body, content_type, api=False):
            self.send_response(status)
            _headers(self, content_type, len(body), api=api)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8", api=True)

        def _guard(self, check_origin=False):
            if not valid_local_host(self.headers.get("Host"), self.server.server_port):
                self._send_json(403, safe_api_error("forbidden"))
                return False
            if check_origin and not _valid_origin(self.headers.get("Origin"), self.server.server_port):
                self._send_json(403, safe_api_error("forbidden"))
                return False
            return True

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self._guard():
                return
            path = urlsplit(self.path).path
            if path in ASSETS:
                filename, content_type = ASSETS[path]
                try:
                    body = (ASSET_DIR / filename).read_bytes()
                except OSError:
                    self._send_json(404, safe_api_error("not_found"))
                    return
                self._send_bytes(200, body, content_type)
                return
            if path == "/favicon.ico":
                self._send_bytes(204, b"", "image/x-icon")
                return
            if path in ("/api/status", "/health"):
                self._send_json(200, {
                    "name": "meaning-intelligence", "version": "1.0.0", "status": "ok",
                    "bind": "127.0.0.1", "offline_default": True,
                    "llm_configured": _llm_configured(), "languages": ["zh", "en"],
                    "approval_default": "pending", "arbitrary_file_or_command_api": False,
                })
                return
            if path == "/api/meta":
                self._send_json(200, {
                    "skills": registry_metadata(),
                    "scales": [{"id": key, "zh": zh, "en": en} for key, zh, en in SCALES],
                    "evidence_levels": list(EVIDENCE_LEVELS), "appendix_d7": list(D7_MODULES),
                    "resources": resource_catalog(),
                })
                return
            self._send_json(404, safe_api_error("not_found"))

        def do_POST(self):
            if not self._guard(check_origin=True):
                return
            path = urlsplit(self.path).path
            if path not in ("/api/analyze", "/api/review"):
                self._send_json(404, safe_api_error("not_found"))
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._send_json(415, safe_api_error("invalid_input"))
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                self._send_json(413, safe_api_error("request_too_large"))
                return
            try:
                payload = strict_json_loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("object required")
                if path == "/api/review" and "previous" in payload:
                    if set(payload) - {"previous", "feedback"} or not isinstance(payload["previous"], dict):
                        raise ValueError("invalid review")
                    result = review(payload["previous"], payload.get("feedback", ""))
                else:
                    allowed = {"text", "context", "use_llm", "approval", "scales"}
                    if set(payload) - allowed:
                        raise ValueError("unexpected field")
                    text = payload.get("text")
                    context = payload.get("context", {})
                    use_llm = payload.get("use_llm", False)
                    approval = payload.get("approval", "pending")
                    scales = payload.get("scales")
                    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                        raise ValueError("invalid text")
                    if not isinstance(context, dict) or not isinstance(use_llm, bool):
                        raise ValueError("invalid options")
                    if scales is not None and (not isinstance(scales, list) or len(scales) > 5 or any(not isinstance(item, str) for item in scales)):
                        raise ValueError("invalid scales")
                    if path.endswith("review") and approval not in APPROVAL_STATES:
                        raise ValueError("invalid approval")
                    if path.endswith("analyze"):
                        result = analyze(text, context=context, scales=scales, use_llm=use_llm)
                    else:
                        result = review(text, context=context, approval=approval, use_llm=use_llm)
                self._send_json(200, result)
            except (ValueError, UnicodeError):
                self._send_json(400, safe_api_error("invalid_input"))
            except Exception:
                self._send_json(500, safe_api_error("internal_error"))

        def do_OPTIONS(self):
            self.send_response(405)
            self.send_header("Allow", "GET, HEAD, POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

    return MeaningAgentServer((host, port), Handler)


def serve(port=DEFAULT_WEB_PORT):
    server = create_server(port)
    host, actual_port = server.server_address[:2]
    print(f"Meaning Agent listening on http://{host}:{actual_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
