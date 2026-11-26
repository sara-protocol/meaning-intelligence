"""Loopback-only transport policy for the Meaning Agent MCP HTTP server.

This module is transport hardening only. It wraps the existing MCP request
handler and does not expose filesystem, shell, or dynamic tool-dispatch APIs.
The bind address is always 127.0.0.1. An optional strong token adds Bearer
authentication for local clients; it never enables a non-loopback bind.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import math
import os
import re
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8767
DEFAULT_MAX_BODY_BYTES = 512 * 1024
DEFAULT_RATE_LIMIT = 60
DEFAULT_RATE_WINDOW_SECONDS = 60.0
MAX_REQUEST_TARGET_BYTES = 2048
MAX_TOKEN_CHARS = 256
MIN_TOKEN_CHARS = 32

_TOKEN_ENV = "MI_MCP_PUBLIC_TOKEN"
_ORIGINS_ENV = "MI_MCP_ALLOWED_ORIGINS"
_DECIMAL = re.compile(r"[0-9]+\Z")
_HEX_TOKEN = re.compile(r"[0-9a-fA-F]{64,}\Z")

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

_ERROR_MESSAGES = {
    "unauthorized": "Authentication is required.",
    "forbidden_origin": "The request origin is not allowed.",
    "not_found": "Resource not found.",
    "method_not_allowed": "Method not allowed.",
    "request_too_large": "Request body is too large.",
    "invalid_request": "Invalid request.",
    "rate_limited": "Too many requests.",
    "internal_error": "Internal error; sensitive details were not returned.",
}


class PublicBindingError(ValueError):
    """A safe configuration error that never includes a supplied token."""


@dataclass(frozen=True)
class BindingConfig:
    host: str
    port: int
    token: str | None = field(default=None, repr=False)
    allowed_origins: frozenset[str] = frozenset()

    @property
    def loopback(self) -> bool:
        return _is_loopback_host(self.host)


@dataclass(frozen=True)
class PublicPolicy:
    token: str | None = field(default=None, repr=False)
    allowed_origins: frozenset[str] = frozenset()
    allowed_paths: tuple[str, ...] = ("/mcp", "/health")
    allowed_methods: tuple[str, ...] = ("GET", "POST", "OPTIONS")
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    rate_limit: int = DEFAULT_RATE_LIMIT
    rate_window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS

    @property
    def auth_required(self) -> bool:
        return self.token is not None


def _is_loopback_host(host: str) -> bool:
    value = host.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if value.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(
        isinstance(address, ipaddress.IPv6Address)
        and address.ipv4_mapped is not None
        and address.ipv4_mapped.is_loopback
    )


def is_strong_token(token: object) -> bool:
    """Return whether a token has adequate length and character variety.

    Accept at least 32 visible ASCII characters with three character classes,
    or a hexadecimal secret of at least 64 characters.  Repeated/placeholder
    values and header whitespace are rejected.  This is a conservative local
    policy, not a password-cracking oracle.
    """

    if not isinstance(token, str) or not MIN_TOKEN_CHARS <= len(token) <= MAX_TOKEN_CHARS:
        return False
    if token != token.strip() or any(not 0x21 <= ord(char) <= 0x7E for char in token):
        return False
    lowered = token.lower()
    if any(marker in lowered for marker in ("placeholder", "changeme", "change-me", "password", "replace-this")):
        return False
    if _HEX_TOKEN.fullmatch(token):
        return len(set(lowered)) >= 8
    classes = (
        any(char.islower() for char in token),
        any(char.isupper() for char in token),
        any(char.isdigit() for char in token),
        any(not char.isalnum() for char in token),
    )
    return sum(classes) >= 3 and len(set(token)) >= 12


def _normalize_origin(value: str) -> str:
    if not value or value != value.strip() or "*" in value:
        raise PublicBindingError(f"{_ORIGINS_ENV} must contain explicit HTTP(S) origins.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise PublicBindingError(f"{_ORIGINS_ENV} contains an invalid origin.") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise PublicBindingError(f"{_ORIGINS_ENV} must contain explicit HTTP(S) origins.")
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise PublicBindingError(f"{_ORIGINS_ENV} contains an invalid hostname.") from exc
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = 443 if parsed.scheme == "https" else 80
    suffix = "" if port is None or port == default_port else f":{port}"
    return f"{parsed.scheme}://{hostname}{suffix}"


def parse_allowed_origins(value: str | None) -> frozenset[str]:
    if value is not None and not isinstance(value, str):
        raise PublicBindingError(f"{_ORIGINS_ENV} must be a comma-separated string.")
    if value is None or not value.strip():
        return frozenset()
    return frozenset(_normalize_origin(item.strip()) for item in value.split(",") if item.strip())


def load_binding_config(
    host: str | None = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    environ: dict[str, str] | None = None,
) -> BindingConfig:
    """Validate bind/token/origin settings without opening a socket."""

    env = os.environ if environ is None else environ
    bind_host = DEFAULT_HOST if host is None else host
    if (
        not isinstance(bind_host, str)
        or not bind_host
        or bind_host != bind_host.strip()
        or any(char.isspace() or ord(char) < 0x21 for char in bind_host)
        or any(char in bind_host for char in "/@\\")
    ):
        raise PublicBindingError("Invalid MCP bind host.")
    if bind_host.startswith("[") and bind_host.endswith("]"):
        bind_host = bind_host[1:-1]
    if bind_host != DEFAULT_HOST:
        raise PublicBindingError("MCP HTTP must bind to 127.0.0.1")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise PublicBindingError("Invalid MCP bind port.")

    raw_token = env.get(_TOKEN_ENV)
    token = None
    if raw_token is not None and raw_token != "":
        if not isinstance(raw_token, str) or not is_strong_token(raw_token):
            raise PublicBindingError(
                f"{_TOKEN_ENV} must be a strong token of at least {MIN_TOKEN_CHARS} characters."
            )
        token = raw_token
    origins = parse_allowed_origins(env.get(_ORIGINS_ENV))
    return BindingConfig(bind_host, port, token, origins)


class SlidingWindowRateLimiter:
    """Small thread-safe per-client sliding-window limiter."""

    def __init__(self, limit: int, window_seconds: float, *, max_clients: int = 4096):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("rate limit must be a positive integer")
        if not isinstance(window_seconds, (int, float)) or not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("rate window must be positive and finite")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self.max_clients = max_clients
        self._clock = time.monotonic
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client: str, *, now: float | None = None) -> tuple[bool, int]:
        current = self._clock() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            if client not in self._buckets and len(self._buckets) >= self.max_clients:
                self._purge_locked(cutoff)
                if len(self._buckets) >= self.max_clients:
                    return False, max(1, math.ceil(self.window_seconds))
            bucket = self._buckets.setdefault(client, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = max(1, math.ceil(bucket[0] + self.window_seconds - current))
                return False, retry_after
            bucket.append(current)
            return True, 0

    def _purge_locked(self, cutoff: float) -> None:
        stale = [client for client, bucket in self._buckets.items() if not bucket or bucket[-1] <= cutoff]
        for client in stale:
            self._buckets.pop(client, None)


class PublicMCPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, policy: PublicPolicy):
        self.public_policy = policy
        self.public_rate_limiter = SlidingWindowRateLimiter(policy.rate_limit, policy.rate_window_seconds)
        super().__init__(address, handler)


class PublicMCPServerV6(PublicMCPServer):
    address_family = socket.AF_INET6


def secure_handler(base_handler: type[BaseHTTPRequestHandler]) -> type[BaseHTTPRequestHandler]:
    """Wrap an existing handler with authentication and transport safeguards."""

    if not issubclass(base_handler, BaseHTTPRequestHandler):
        raise TypeError("base_handler must be a BaseHTTPRequestHandler subclass")

    class PublicMCPHandler(base_handler):
        protocol_version = "HTTP/1.1"
        server_version = "MeaningAgentMCP"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(15)
            self.public_cors_origin = None
            self.public_headers_sent = False

        def log_message(self, format, *args):
            # Request targets and headers can contain secrets; do not log them.
            return

        def version_string(self):
            return self.server_version

        def send_error(self, code, message=None, explain=None):
            # Replace stdlib HTML/parser errors, which can echo raw request
            # lines, with fixed JSON messages that contain no request data.
            category = "method_not_allowed" if code == 501 else "invalid_request"
            self._send_public_error(code, category)

        def end_headers(self):
            origin = getattr(self, "public_cors_origin", None)
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
            if self.server.public_policy.allowed_origins:
                self.send_header("Vary", "Origin")
            for key, value in _SECURITY_HEADERS.items():
                self.send_header(key, value)
            super().end_headers()
            self.public_headers_sent = True

        def do_GET(self):
            self._handle_public("GET")

        def do_POST(self):
            self._handle_public("POST")

        def do_OPTIONS(self):
            self._handle_preflight()

        def __getattr__(self, name):
            # BaseHTTPRequestHandler otherwise returns 501 for unknown verbs
            # before any policy check.  Route every verb through the guard.
            if name.startswith("do_"):
                method = name[3:]
                return lambda: self._handle_public(method)
            raise AttributeError(name)

        def _handle_public(self, method: str):
            if not self._rate_allowed():
                return
            if not self._authenticated():
                return
            if not self._request_allowed(method):
                return
            if method == "GET" and self.path == "/health":
                self._send_health()
                return
            try:
                delegate = getattr(super(), f"do_{method}", None)
                if delegate is None:
                    self._send_public_error(405, "method_not_allowed")
                    return
                delegate()
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Exception:
                self.close_connection = True
                if not getattr(self, "public_headers_sent", False):
                    # Discard any partially buffered headers before replacing them.
                    if hasattr(self, "_headers_buffer"):
                        self._headers_buffer.clear()
                    try:
                        self._send_public_error(500, "internal_error")
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass

        def _send_health(self):
            body = json.dumps(
                {"status": "ok", "service": "meaning-intelligence-mcp"},
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        def _handle_preflight(self):
            # Browser preflight carries no Bearer credential and returns no
            # resource data.  It is the sole unauthenticated transport method.
            if not self._rate_allowed():
                return
            if not self._request_allowed("OPTIONS"):
                return
            requested_method = self.headers.get("Access-Control-Request-Method", "").upper()
            if requested_method not in ("GET", "POST"):
                self._send_public_error(403, "forbidden_origin")
                return
            requested_headers = self.headers.get("Access-Control-Request-Headers", "")
            headers = [item.strip().lower() for item in requested_headers.split(",") if item.strip()]
            if any(item not in ("authorization", "content-type", "accept") for item in headers):
                self._send_public_error(403, "forbidden_origin")
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True

        def _rate_allowed(self) -> bool:
            client = str(self.client_address[0]) if self.client_address else "unknown"
            allowed, retry_after = self.server.public_rate_limiter.check(client)
            if not allowed:
                self._send_public_error(429, "rate_limited", retry_after=retry_after)
            return allowed

        def _authenticated(self) -> bool:
            expected = self.server.public_policy.token
            if expected is None:
                return True
            values = self.headers.get_all("Authorization") or []
            if len(values) != 1:
                self._send_public_error(401, "unauthorized")
                return False
            scheme, separator, supplied = values[0].partition(" ")
            if not separator or scheme.lower() != "bearer" or not supplied or any(char.isspace() for char in supplied):
                self._send_public_error(401, "unauthorized")
                return False
            if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
                self._send_public_error(401, "unauthorized")
                return False
            return True

        def _request_allowed(self, method: str) -> bool:
            if method not in self.server.public_policy.allowed_methods:
                self._send_public_error(405, "method_not_allowed")
                return False
            target = self.path or ""
            if len(target.encode("utf-8", errors="replace")) > MAX_REQUEST_TARGET_BYTES:
                self._send_public_error(414, "invalid_request")
                return False
            if not target.startswith("/") or "#" in target or "?" in target:
                self._send_public_error(404, "not_found")
                return False
            try:
                path = unquote(urlsplit(target).path, errors="strict")
            except (UnicodeError, ValueError):
                self._send_public_error(404, "not_found")
                return False
            # API routes are literal.  Refusing encoded paths also rejects
            # single/double-encoded traversal before a delegate sees them.
            if path != target or path not in self.server.public_policy.allowed_paths:
                self._send_public_error(404, "not_found")
                return False

            origins = self.headers.get_all("Origin") or []
            if len(origins) > 1:
                self._send_public_error(403, "forbidden_origin")
                return False
            if origins:
                origin = origins[0]
                if origin not in self.server.public_policy.allowed_origins:
                    self._send_public_error(403, "forbidden_origin")
                    return False
                self.public_cors_origin = origin

            transfer_encodings = self.headers.get_all("Transfer-Encoding") or []
            lengths = self.headers.get_all("Content-Length") or []
            if transfer_encodings:
                self._send_public_error(400, "invalid_request")
                return False
            if len(lengths) > 1:
                self._send_public_error(400, "invalid_request")
                return False
            if lengths:
                raw_length = lengths[0]
                if not _DECIMAL.fullmatch(raw_length) or len(raw_length) > 20:
                    self._send_public_error(400, "invalid_request")
                    return False
                length = int(raw_length)
                if length > self.server.public_policy.max_body_bytes:
                    self._send_public_error(413, "request_too_large")
                    return False
                if method != "POST" and length != 0:
                    self._send_public_error(400, "invalid_request")
                    return False
            elif method == "POST":
                self._send_public_error(411, "invalid_request")
                return False
            return True

        def _send_public_error(self, status: int, code: str, **headers):
            body = json.dumps(
                {"error": {"code": code, "message": _ERROR_MESSAGES[code]}},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            if status == 401:
                self.send_header("WWW-Authenticate", "Bearer")
            if status == 405:
                self.send_header("Allow", "GET, POST, OPTIONS")
            for key, value in headers.items():
                self.send_header(key.replace("_", "-"), str(value))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

    # Also replace verbs implemented by the delegate (for example DELETE), so
    # none can bypass authentication by being inherited unchanged.
    for method_name in dir(base_handler):
        if method_name.startswith("do_") and method_name not in ("do_GET", "do_POST", "do_OPTIONS"):
            method = method_name[3:]

            def guarded_method(self, method=method):
                self._handle_public(method)

            setattr(PublicMCPHandler, method_name, guarded_method)

    PublicMCPHandler.__name__ = f"Public{base_handler.__name__}"
    PublicMCPHandler.__qualname__ = PublicMCPHandler.__name__
    return PublicMCPHandler


def create_server(
    base_handler: type[BaseHTTPRequestHandler],
    *,
    host: str | None = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    rate_limit: int = DEFAULT_RATE_LIMIT,
    rate_window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS,
    allowed_paths: tuple[str, ...] = ("/mcp", "/health"),
    allowed_methods: tuple[str, ...] = ("GET", "POST", "OPTIONS"),
    environ: dict[str, str] | None = None,
) -> PublicMCPServer:
    """Create a server around an existing MCP handler, defaulting to loopback."""

    config = load_binding_config(host, port, environ)
    if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes < 1:
        raise PublicBindingError("Invalid MCP request size limit.")
    if not allowed_paths or any(not path.startswith("/") or "?" in path or "#" in path for path in allowed_paths):
        raise PublicBindingError("Invalid MCP path allowlist.")
    if not allowed_methods or any(method not in ("GET", "POST", "OPTIONS") for method in allowed_methods):
        raise PublicBindingError("Invalid MCP method allowlist.")
    policy = PublicPolicy(
        token=config.token,
        allowed_origins=config.allowed_origins,
        allowed_paths=tuple(allowed_paths),
        allowed_methods=tuple(allowed_methods),
        max_body_bytes=max_body_bytes,
        rate_limit=rate_limit,
        rate_window_seconds=rate_window_seconds,
    )
    handler = secure_handler(base_handler)
    server_class = PublicMCPServerV6 if ":" in config.host else PublicMCPServer
    return server_class((config.host, config.port), handler, policy)


def serve(
    base_handler: type[BaseHTTPRequestHandler],
    *,
    host: str | None = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    **options,
) -> None:
    """Run the wrapped MCP handler; never print credentials or request data."""

    server = create_server(base_handler, host=host, port=port, **options)
    bound_host, actual_port = server.server_address[:2]
    display_host = f"[{bound_host}]" if ":" in bound_host else bound_host
    auth_state = "required" if server.public_policy.auth_required else "not required"
    print(
        f"Meaning Agent MCP listening on http://{display_host}:{actual_port}; authentication {auth_state}.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class CoreMCPHandler(BaseHTTPRequestHandler):
    """Thin HTTP adapter for the existing RPC core, without tool duplication.

    Imports are lazy so the concurrently maintained ``mcp_server`` module can
    also import this loopback-only transport policy without creating an import cycle.
    The outer handler owns binding, authentication, CORS, size, and rate limits.
    """

    protocol_version = "HTTP/1.1"
    server_version = "MeaningMCP/1.0"
    sys_version = ""

    def log_message(self, format, *args):
        return

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_POST(self):
        from .mcp_server import handle_jsonrpc
        from .safety import strict_json_loads

        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._send(415, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Content-Type must be application/json"}})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            request = strict_json_loads(self.rfile.read(length).decode("utf-8"))
            response = handle_jsonrpc(request)
        except (ValueError, UnicodeError):
            self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            return
        except Exception:
            self._send(500, {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal error"}})
            return
        if response is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send(200, response)


def create_core_server(*, host: str | None = DEFAULT_HOST, port: int = DEFAULT_PORT, **options) -> PublicMCPServer:
    """Create the secured HTTP transport around the existing MCP RPC core."""

    return create_server(CoreMCPHandler, host=host, port=port, **options)


def serve_core(*, host: str | None = DEFAULT_HOST, port: int = DEFAULT_PORT, **options) -> None:
    """Serve the existing read-only MCP core on loopback only."""

    serve(CoreMCPHandler, host=host, port=port, **options)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Secure Meaning Agent MCP HTTP transport")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host; only 127.0.0.1 is allowed")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        serve_core(host=args.host, port=args.port)
    except (PublicBindingError, OSError, ValueError):
        print("meaning-agent-mcp: invalid configuration or bind failure; no sensitive details were returned.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
