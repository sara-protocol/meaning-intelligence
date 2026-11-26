"""Read-only Meaning Intelligence MCP over HTTP JSON-RPC and stdio."""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .catalog import RESOURCES, read_resource, resource_catalog
from .engine import APPROVAL_STATES, analyze, review
from .i18n import bi
from .safety import MAX_BODY_BYTES, MAX_JSONRPC_LINE, safe_error, strict_json_loads, valid_local_host

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "meaning-intelligence", "version": "1.0.0"}
TEXT_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 20000}
CONTEXT_SCHEMA = {"type": "object", "maxProperties": 100}
TOOLS = [
    {
        "name": "meaning_analyze",
        "description": bi("运行六层只读分析；默认离线，人类批准保持 pending。", "Run six-layer read-only analysis; offline by default with human approval pending."),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["text"],
            "properties": {
                "text": TEXT_SCHEMA,
                "context": CONTEXT_SCHEMA,
                "use_llm": {"type": "boolean", "default": False, "description": bi("仅显式开启已配置 LLM。", "Enable the configured LLM only when explicit.")},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "meaning_review",
        "description": bi("运行递归审视与可逆归零；不执行修订。", "Run recursive review and reversible zeroing; never execute revisions."),
        "inputSchema": {
            "type": "object", "additionalProperties": False,
            "required": ["text"],
            "properties": {
                "text": TEXT_SCHEMA,
                "context": CONTEXT_SCHEMA,
                "approval": {"type": "string", "enum": list(APPROVAL_STATES), "default": "pending"},
                "use_llm": {"type": "boolean", "default": False},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]


class RPCError(Exception):
    def __init__(self, code, message, category="invalid_request"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category


def _error(request_id, code, message, category="invalid_request"):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message, "data": {"code": category}}}


def _validate_arguments(arguments, review_tool=False):
    if not isinstance(arguments, dict):
        raise RPCError(-32602, "Invalid params", "invalid_input")
    allowed = {"text", "context", "use_llm"} | ({"approval"} if review_tool else set())
    if set(arguments) - allowed:
        raise RPCError(-32602, "Invalid params", "invalid_input")
    if not isinstance(arguments.get("text"), str) or not arguments["text"].strip():
        raise RPCError(-32602, "Invalid params", "invalid_input")
    if len(arguments["text"]) > 20000:
        raise RPCError(-32602, "Invalid params", "request_too_large")
    if "context" in arguments and not isinstance(arguments["context"], dict):
        raise RPCError(-32602, "Invalid params", "invalid_input")
    if "use_llm" in arguments and not isinstance(arguments["use_llm"], bool):
        raise RPCError(-32602, "Invalid params", "invalid_input")
    if review_tool and arguments.get("approval", "pending") not in APPROVAL_STATES:
        raise RPCError(-32602, "Invalid params", "invalid_input")


def _tool_result(value):
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": value,
        "isError": False,
    }


def handle_jsonrpc(request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        return _error(request.get("id") if isinstance(request, dict) else None, -32600, "Invalid Request")
    request_id = request.get("id")
    notification = "id" not in request
    method = request["method"]
    params = request.get("params", {})
    try:
        if method == "initialize":
            if not isinstance(params, dict):
                raise RPCError(-32602, "Invalid params")
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"resources": {"subscribe": False, "listChanged": False}, "tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": bi("只读资源与分析工具；不执行代码，不访问任意路径。", "Read-only resources and analysis tools; no code execution or arbitrary paths."),
            }
        elif method == "ping":
            result = {}
        elif method == "resources/list":
            result = {"resources": RESOURCES}
        elif method == "resources/read":
            if not isinstance(params, dict) or not isinstance(params.get("uri"), str):
                raise RPCError(-32602, "Invalid params")
            document = read_resource(params["uri"])
            if document is None:
                raise RPCError(-32002, "Resource not found", "not_found")
            result = {"contents": [{"uri": params["uri"], "mimeType": "application/json", "text": json.dumps(document, ensure_ascii=False, allow_nan=False)}]}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                raise RPCError(-32602, "Invalid params")
            name = params["name"]
            arguments = params.get("arguments", {})
            if name == "meaning_analyze":
                _validate_arguments(arguments)
                result = _tool_result(analyze(arguments["text"], context=arguments.get("context", {}), use_llm=arguments.get("use_llm", False)))
            elif name == "meaning_review":
                _validate_arguments(arguments, review_tool=True)
                result = _tool_result(review(arguments["text"], context=arguments.get("context", {}), approval=arguments.get("approval", "pending"), use_llm=arguments.get("use_llm", False)))
            else:
                raise RPCError(-32602, "Unknown tool", "not_found")
        elif method in ("notifications/initialized", "notifications/cancelled"):
            result = None
        else:
            raise RPCError(-32601, "Method not found", "not_found")
    except RPCError as exc:
        return None if notification else _error(request_id, exc.code, exc.message, exc.category)
    except ValueError:
        return None if notification else _error(request_id, -32602, "Invalid params", "invalid_input")
    except Exception:
        return None if notification else _error(request_id, -32603, "Internal error", "internal_error")
    if notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve_stdio():
    source = sys.stdin.buffer
    target = sys.stdout.buffer
    while True:
        line = source.readline(MAX_JSONRPC_LINE + 1)
        if not line:
            return
        request_id = None
        if len(line) > MAX_JSONRPC_LINE:
            response = _error(None, -32600, "Request too large", "request_too_large")
        else:
            try:
                request = strict_json_loads(line.decode("utf-8"))
                if isinstance(request, dict):
                    request_id = request.get("id")
                response = handle_jsonrpc(request)
            except Exception:
                response = _error(request_id, -32700, "Parse error", "invalid_response")
        if response is not None:
            target.write(json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n")
            target.flush()


def _security_headers(handler):
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")


def create_http_server(port, host="127.0.0.1"):
    if host != "127.0.0.1":
        raise ValueError("MCP HTTP must bind to 127.0.0.1")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    class Handler(BaseHTTPRequestHandler):
        server_version = "MeaningMCP/1.0"
        sys_version = ""

        def log_message(self, format, *args):
            return

        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            _security_headers(self)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/mcp":
                self._send(404, _error(None, -32601, "Not found", "not_found"))
                return
            if not valid_local_host(self.headers.get("Host"), port):
                self._send(403, _error(None, -32603, "Forbidden", "forbidden"))
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._send(415, _error(None, -32600, "Content-Type must be application/json", "invalid_input"))
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                self._send(413, _error(None, -32600, "Invalid body size", "request_too_large"))
                return
            try:
                request = strict_json_loads(self.rfile.read(length).decode("utf-8"))
                response = handle_jsonrpc(request)
                if response is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    _security_headers(self)
                    self.end_headers()
                else:
                    self._send(200, response)
            except Exception:
                self._send(400, _error(None, -32700, "Parse error", "invalid_response"))

        def do_GET(self):
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            _security_headers(self)
            self.end_headers()

        def do_OPTIONS(self):
            self.do_GET()

    return ThreadingHTTPServer((host, port), Handler)


def serve_http(port):
    server = create_http_server(port)
    print(f"Meaning Agent MCP listening on http://127.0.0.1:{port}/mcp", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
