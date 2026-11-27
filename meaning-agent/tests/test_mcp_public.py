from __future__ import annotations

import contextlib
import hmac
import http.client
import io
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest import mock
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meaning_agent.mcp_public import (  # noqa: E402
    DEFAULT_HOST,
    CoreMCPHandler,
    PublicBindingError,
    SlidingWindowRateLimiter,
    create_server,
    is_strong_token,
    load_binding_config,
    parse_allowed_origins,
)

STRONG_TOKEN = "MI-Public-Token-2026-Correct-Horse-Battery-Staple-42"
WRONG_TOKEN = "MI-Public-Token-2026-Wrong-Horse-Battery-Staple-84"
ALLOWED_ORIGIN = "https://console.example"


class DummyCoreHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        return

    def send_value(self, status, value):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.server.delegate_calls += 1
        if urlsplit(self.path).path == "/health":
            self.send_value(200, {"status": "ok"})
            return
        if urlsplit(self.path).path == "/mcp":
            self.send_value(200, {"tools": ["mi_catalog", "mi_content", "mi_analyze", "mi_review"]})
            return
        self.send_value(404, {"error": "not_found"})

    def do_POST(self):
        self.server.delegate_calls += 1
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self.send_value(200, {"bytes": len(raw), "json": json.loads(raw)})

    def do_DELETE(self):
        self.server.delegate_calls += 1
        self.send_value(200, {"deleted": True})


@contextlib.contextmanager
def running_server(*, env=None, handler=DummyCoreHandler, **options):
    server = create_server(
        handler,
        host="127.0.0.1",
        port=0,
        environ={} if env is None else env,
        **options,
    )
    server.delegate_calls = 0
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, method, path, *, body=None, headers=None):
    request_headers = dict(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        try:
            value = json.loads(raw) if raw else None
        except (ValueError, UnicodeError):
            value = raw
        return response.status, value, response_headers
    finally:
        connection.close()


def auth(token=STRONG_TOKEN):
    return {"Authorization": f"Bearer {token}"}


class BindingConfigTests(unittest.TestCase):
    def test_loopback_is_default_and_needs_no_token(self):
        config = load_binding_config(environ={})
        self.assertEqual(config.host, DEFAULT_HOST)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertIsNone(config.token)
        with running_server() as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertEqual(request(server, "GET", "/health")[0], 200)

    def test_every_non_loopback_bind_is_rejected_even_with_token(self):
        for host in ("0.0.0.0", "::", "localhost", "::1", "192.0.2.10", "eth0"):
            for env in ({}, {"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}):
                with self.subTest(host=host, authenticated=bool(env)):
                    with self.assertRaises(PublicBindingError):
                        load_binding_config(host, environ=env)

    def test_missing_empty_and_weak_tokens_are_rejected_without_echo(self):
        weak_tokens = ("short", "a" * 40, "abcdefghijklmnopqrstuvwxyz123456", "placeholder-token-please-replace-123")
        for token in weak_tokens:
            with self.subTest(token_length=len(token)):
                with self.assertRaises(PublicBindingError) as caught:
                    load_binding_config("127.0.0.1", environ={"MI_MCP_PUBLIC_TOKEN": token})
                self.assertNotIn(token, str(caught.exception))

    def test_strong_token_is_accepted_but_hidden_from_repr(self):
        config = load_binding_config("127.0.0.1", environ={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN})
        self.assertEqual(config.token, STRONG_TOKEN)
        self.assertNotIn(STRONG_TOKEN, repr(config))
        self.assertTrue(is_strong_token("Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0Qr2St3Uv"))
        self.assertTrue(is_strong_token("0123456789abcdef" * 4))
        self.assertFalse(is_strong_token("A1!" * 8 + "abcdefgh"))
        self.assertFalse(is_strong_token("AbCdEfGhIjKlMnOpQrStUvWxYz"))

    def test_origin_allowlist_is_explicit_and_normalized(self):
        origins = parse_allowed_origins("https://EXAMPLE.com:443, http://localhost:8080")
        self.assertEqual(origins, frozenset({"https://example.com", "http://localhost:8080"}))
        for value in ("*", "https://*.example.com", "https://example.com/path", "null", "file:///tmp/x"):
            with self.subTest(value=value):
                with self.assertRaises(PublicBindingError):
                    parse_allowed_origins(value)


class AuthenticationTests(unittest.TestCase):
    def test_missing_and_wrong_tokens_are_rejected_on_health_and_mcp(self):
        env = {"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}
        with running_server(env=env) as server:
            missing = request(server, "GET", "/health")
            wrong = request(server, "GET", "/health", headers=auth(WRONG_TOKEN))
            self.assertEqual(missing[0], 401)
            self.assertEqual(wrong[0], 401)
            self.assertEqual(missing[1], wrong[1])
            self.assertEqual(missing[2]["www-authenticate"], "Bearer")
            self.assertEqual(request(server, "GET", "/health", headers=auth())[0], 200)
            self.assertEqual(request(server, "GET", "/unknown")[0], 401)
            self.assertEqual(request(server, "POST", "/mcp", body={}, headers=auth(WRONG_TOKEN))[0], 401)
            self.assertEqual(server.delegate_calls, 0)

    def test_wrong_token_uses_constant_time_comparison(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            with mock.patch("meaning_agent.mcp_public.hmac.compare_digest", wraps=hmac.compare_digest) as compare:
                self.assertEqual(request(server, "GET", "/health", headers=auth(WRONG_TOKEN))[0], 401)
            compare.assert_called_once()

    def test_duplicate_authorization_headers_are_rejected(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                connection.putrequest("GET", "/health")
                connection.putheader("Authorization", f"Bearer {STRONG_TOKEN}")
                connection.putheader("Authorization", f"Bearer {STRONG_TOKEN}")
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 401)
                response.read()
            finally:
                connection.close()

    def test_token_is_not_logged_or_returned_in_sanitized_errors(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                response = request(server, "GET", "/health", headers=auth(WRONG_TOKEN))
                self.assertEqual(response[0], 401)
                self.assertNotIn(STRONG_TOKEN, json.dumps(response[1]))
                self.assertNotIn(WRONG_TOKEN, json.dumps(response[1]))
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(STRONG_TOKEN, combined)
        self.assertNotIn(WRONG_TOKEN, combined)


class OriginAndMethodTests(unittest.TestCase):
    def test_allowed_origin_gets_exact_cors_header_and_others_are_rejected(self):
        env = {"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN, "MI_MCP_ALLOWED_ORIGINS": ALLOWED_ORIGIN}
        with running_server(env=env) as server:
            allowed = request(server, "GET", "/health", headers={**auth(), "Origin": ALLOWED_ORIGIN})
            denied = request(server, "GET", "/health", headers={**auth(), "Origin": "https://evil.example"})
            self.assertEqual(allowed[0], 200)
            self.assertEqual(allowed[2]["access-control-allow-origin"], ALLOWED_ORIGIN)
            self.assertNotEqual(allowed[2]["access-control-allow-origin"], "*")
            self.assertEqual(denied[0], 403)
            self.assertNotIn("access-control-allow-origin", denied[2])

    def test_host_guard_prevents_dns_rebinding(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            valid_host = f"127.0.0.1:{server.server_port}"
            self.assertEqual(request(server, "GET", "/health", headers={**auth(), "Host": valid_host})[0], 200)
            for host in (
                "evil.example",
                f"127.0.0.1:{server.server_port + 1}",
                f"attacker@{valid_host}",
                f"{valid_host}/mcp",
            ):
                with self.subTest(host=host):
                    self.assertEqual(request(server, "GET", "/health", headers={**auth(), "Host": host})[0], 403)
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
                connection.sendall(
                    (
                        "GET /health HTTP/1.1\r\n"
                        f"Host: {valid_host}\r\n"
                        f"Host: {valid_host}\r\n"
                        f"Authorization: Bearer {STRONG_TOKEN}\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode("ascii")
                )
                self.assertIn(b" 403 ", connection.recv(4096).split(b"\r\n", 1)[0])
            self.assertEqual(server.delegate_calls, 0)

    def test_browser_origin_is_rejected_without_an_allowlist(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            response = request(server, "GET", "/health", headers={**auth(), "Origin": ALLOWED_ORIGIN})
            self.assertEqual(response[0], 403)

    def test_preflight_is_data_free_and_validates_method_and_headers(self):
        env = {"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN, "MI_MCP_ALLOWED_ORIGINS": ALLOWED_ORIGIN}
        with running_server(env=env) as server:
            headers = {
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type",
            }
            response = request(server, "OPTIONS", "/mcp", headers=headers)
            self.assertEqual(response[0], 204)
            self.assertEqual(response[2]["access-control-allow-origin"], ALLOWED_ORIGIN)
            self.assertNotIn("*", response[2]["access-control-allow-origin"])
            denied = request(server, "OPTIONS", "/mcp", headers={**headers, "Access-Control-Request-Method": "DELETE"})
            self.assertEqual(denied[0], 403)
            bad_header = request(server, "OPTIONS", "/mcp", headers={**headers, "Access-Control-Request-Headers": "x-evil"})
            self.assertEqual(bad_header[0], 403)

    def test_unsafe_and_unknown_methods_cannot_reach_the_delegate(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            for method in ("PUT", "PATCH", "DELETE", "TRACE", "PROPFIND"):
                with self.subTest(method=method):
                    response = request(server, method, "/mcp", headers=auth())
                    self.assertEqual(response[0], 405)
                    self.assertEqual(response[2]["allow"], "GET, POST, OPTIONS")
            self.assertEqual(server.delegate_calls, 0)

    def test_traversal_and_encoded_paths_are_rejected(self):
        paths = (
            "/mcp/../../etc/passwd",
            "/mcp/%2e%2e/%2e%2e/etc/passwd",
            "/mcp/%252e%252e/etc/passwd",
            "/mcp\\..\\..\\etc\\passwd",
            "/mcp?path=/etc/passwd",
            "//etc/passwd",
        )
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            for path in paths:
                with self.subTest(path=path):
                    self.assertEqual(request(server, "GET", path, headers=auth())[0], 404)
            self.assertEqual(server.delegate_calls, 0)


class RequestSafeguardTests(unittest.TestCase):
    def test_request_size_cap_and_chunked_requests_are_rejected(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, max_body_bytes=128) as server:
            oversized = request(server, "POST", "/mcp", body=b"x" * 129, headers=auth())
            self.assertEqual(oversized[0], 413)
            exact = request(server, "POST", "/mcp", body=b"{}" + b" " * 126, headers=auth())
            self.assertEqual(exact[0], 200)

            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                connection.request(
                    "POST",
                    "/mcp",
                    body=iter([b"{}"]),
                    headers={**auth(), "Content-Type": "application/json", "Transfer-Encoding": "chunked"},
                    encode_chunked=True,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
            finally:
                connection.close()

    def test_negative_content_length_is_rejected(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
                connection.sendall(
                    (
                        "POST /mcp HTTP/1.1\r\n"
                        f"Host: 127.0.0.1:{server.server_port}\r\n"
                        f"Authorization: Bearer {STRONG_TOKEN}\r\n"
                        "Content-Length: -1\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode("ascii")
                )
                raw = connection.recv(4096)
            self.assertIn(b" 400 ", raw.split(b"\r\n", 1)[0])

    def test_malformed_parser_errors_do_not_echo_request_data(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}) as server:
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=3) as connection:
                connection.sendall(f"GET /{STRONG_TOKEN} bad\r\nConnection: close\r\n\r\n".encode("ascii"))
                chunks = []
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
            self.assertIn(b" 400 ", raw.split(b"\r\n", 1)[0])
            self.assertNotIn(STRONG_TOKEN.encode("ascii"), raw)
            self.assertIn(b'"code":"invalid_request"', raw)

    def test_rate_limit_returns_429_and_retry_after(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, rate_limit=2, rate_window_seconds=60) as server:
            self.assertEqual(request(server, "GET", "/health", headers=auth())[0], 200)
            self.assertEqual(request(server, "GET", "/health", headers=auth())[0], 200)
            limited = request(server, "GET", "/health", headers=auth())
            self.assertEqual(limited[0], 429)
            self.assertGreaterEqual(int(limited[2]["retry-after"]), 1)
            self.assertEqual(server.delegate_calls, 0)

    def test_rate_limiter_is_per_client_and_sliding(self):
        limiter = SlidingWindowRateLimiter(2, 10)
        self.assertEqual(limiter.check("a", now=0), (True, 0))
        self.assertEqual(limiter.check("a", now=1), (True, 0))
        self.assertEqual(limiter.check("a", now=2), (False, 8))
        self.assertEqual(limiter.check("b", now=2), (True, 0))
        self.assertEqual(limiter.check("a", now=11), (True, 0))

    def test_delegate_exception_becomes_sanitized_internal_error(self):
        class BrokenHandler(DummyCoreHandler):
            def do_GET(self):
                raise RuntimeError(f"private detail {STRONG_TOKEN}")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, handler=BrokenHandler) as server:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                response = request(server, "GET", "/mcp", headers=auth())
        self.assertEqual(response[0], 500)
        self.assertEqual(response[1]["error"]["code"], "internal_error")
        self.assertNotIn(STRONG_TOKEN, json.dumps(response[1]))
        self.assertNotIn("private detail", json.dumps(response[1]))
        self.assertNotIn(STRONG_TOKEN, stdout.getvalue() + stderr.getvalue())


class MCPCoreIntegrationTests(unittest.TestCase):
    def rpc(self, server, method, params=None, request_id=1):
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        status, response, _ = request(server, "POST", "/mcp", body=payload, headers=auth())
        self.assertEqual(status, 200)
        return response

    def test_secured_transport_exposes_only_catalog_and_analysis_tools(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, handler=CoreMCPHandler) as server:
            self.assertEqual(request(server, "POST", "/mcp", body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})[0], 401)
            tools = self.rpc(server, "tools/list")["result"]["tools"]
            self.assertEqual({tool["name"] for tool in tools}, {"meaning_analyze", "meaning_review"})
            for tool in tools:
                self.assertTrue(tool["annotations"]["readOnlyHint"])
                self.assertFalse(tool["annotations"]["destructiveHint"])
            resources = self.rpc(server, "resources/list")["result"]["resources"]
            self.assertTrue(resources)
            self.assertTrue(all(resource["uri"].startswith("meaning://") for resource in resources))
            catalog = self.rpc(server, "resources/read", {"uri": "meaning://catalog"})["result"]["contents"][0]
            document = json.loads(catalog["text"])
            self.assertEqual(document["tools"], ["meaning_analyze", "meaning_review"])

    def test_arbitrary_file_and_command_requests_have_no_tool_or_resource(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, handler=CoreMCPHandler) as server:
            for uri in ("file:///etc/passwd", "meaning://skills/../../etc/passwd", "/etc/passwd"):
                with self.subTest(uri=uri):
                    response = self.rpc(server, "resources/read", {"uri": uri})
                    self.assertEqual(response["error"]["code"], -32002)
            for name in ("read_file", "execute", "shell"):
                with self.subTest(tool=name):
                    response = self.rpc(server, "tools/call", {"name": name, "arguments": {"path": "/etc/passwd", "command": "whoami"}})
                    self.assertEqual(response["error"]["code"], -32602)

    def test_analyze_and_review_remain_non_executing_over_public_wrapper(self):
        with running_server(env={"MI_MCP_PUBLIC_TOKEN": STRONG_TOKEN}, handler=CoreMCPHandler) as server:
            analysis = self.rpc(server, "tools/call", {
                "name": "meaning_analyze",
                "arguments": {"text": "A synthetic claim needs evidence and human review.", "use_llm": False},
            })["result"]["structuredContent"]
            self.assertFalse(analysis["safety"]["arbitrary_file_or_command_execution"])
            self.assertFalse(analysis["approval"]["execution_authorized"])
            review = self.rpc(server, "tools/call", {
                "name": "meaning_review",
                "arguments": {"text": "A synthetic claim needs evidence and human review.", "use_llm": False},
            })["result"]["structuredContent"]
            self.assertFalse(review["execution"]["performed"])
            self.assertFalse(review["approval"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
