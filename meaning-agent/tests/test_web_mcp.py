import http.client
import json
import os
import socket
import threading
import unittest
from unittest.mock import patch

from meaning_agent.mcp_server import create_http_server as create_mcp_server, handle_jsonrpc
from meaning_agent.safety import MAX_BODY_BYTES
from meaning_agent.web import create_server as create_web_server


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ServerFixture(unittest.TestCase):
    def start(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def request(self, port, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        request_headers = dict(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        result_headers = dict(response.getheaders())
        status = response.status
        connection.close()
        return status, result_headers, data


class WebTests(ServerFixture):
    def setUp(self):
        self.port = self.start(create_web_server(free_port()))

    def test_ui_assets_and_security_headers(self):
        status, headers, body = self.request(self.port, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="lang-zh"', body)
        self.assertIn(b'id="lang-en"', body)
        self.assertIn("Content-Security-Policy", headers)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for path, marker in (("/styles.css", b"@media (max-width: 780px)"), ("/app.js", b"/api/")):
            asset_status, _, asset = self.request(self.port, "GET", path)
            self.assertEqual(asset_status, 200)
            self.assertIn(marker, asset)

    def test_status_and_analysis_api(self):
        status, _, body = self.request(self.port, "GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["llm_configured"])
        payload = {"text": "个人希望自主，组织担心成本。是否暂停？", "use_llm": False}
        status, _, body = self.request(self.port, "POST", "/api/analyze", payload, {"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(list(result["skills"]), [f"L{i}" for i in range(1, 7)])
        self.assertEqual(result["approval"]["status"], "pending")

    def test_review_api_records_approval_without_execution(self):
        status, _, body = self.request(self.port, "POST", "/api/review", {"text": "A claim needs review.", "approval": "approved", "use_llm": False})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertFalse(result["execution"]["performed"])

    def test_traversal_and_unknown_paths_rejected(self):
        for path in ("/../safety.py", "/%2e%2e/safety.py", "/meaning_agent/safety.py", "/api/exec"):
            with self.subTest(path=path):
                status, _, body = self.request(self.port, "GET", path)
                self.assertEqual(status, 404)
                self.assertEqual(json.loads(body)["error"]["code"], "not_found")

    def test_host_origin_and_size_guards(self):
        status, _, _ = self.request(self.port, "GET", "/", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request(self.port, "POST", "/api/analyze", {"text": "x"}, {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _, body = self.request(self.port, "POST", "/api/analyze", b"", {"Content-Type": "application/json", "Content-Length": str(MAX_BODY_BYTES + 1)})
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["error"]["code"], "request_too_large")

    def test_invalid_json_and_unexpected_fields(self):
        status, _, _ = self.request(self.port, "POST", "/api/analyze", b"{", {"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        status, _, _ = self.request(self.port, "POST", "/api/analyze", {"text": "x", "command": "calc"}, {"Content-Type": "application/json"})
        self.assertEqual(status, 400)

    def test_no_key_leakage_in_status_or_output(self):
        secret = "sk-test-SECRET123456"
        with patch.dict(os.environ, {"MI_LLM_API_KEY": secret}, clear=False):
            _, _, status_body = self.request(self.port, "GET", "/api/status")
            _, _, body = self.request(self.port, "POST", "/api/analyze", {"text": f"api_key={secret}。研究显示效果。", "use_llm": False})
        self.assertNotIn(secret.encode(), status_body)
        self.assertNotIn(secret.encode(), body)
        self.assertIn(b"[REDACTED]", body)


class MCPTests(ServerFixture):
    def setUp(self):
        self.port = self.start(create_mcp_server(free_port()))

    def rpc(self, request):
        status, _, body = self.request(self.port, "POST", "/mcp", request)
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_initialize_and_catalog(self):
        initialized = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(initialized["result"]["protocolVersion"], "2024-11-05")
        resources = self.rpc({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})["result"]["resources"]
        self.assertEqual(len(resources), 10)
        catalog = self.rpc({"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "meaning://catalog"}})
        document = json.loads(catalog["result"]["contents"][0]["text"])
        self.assertIn("zh", document["title"])
        self.assertIn("en", document["title"])

    def test_skill_resource_is_bilingual(self):
        response = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "meaning://skills/calibrate-five-scales"}})
        document = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(document["skill"]["layer"], "L5")
        self.assertIn("zh", document["workflow"])
        self.assertIn("en", document["workflow"])

    def test_analyze_and_review_tools(self):
        tools = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in tools))
        response = self.rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "meaning_analyze", "arguments": {"text": "A claim lacks evidence.", "use_llm": False}}})
        result = response["result"]["structuredContent"]
        self.assertEqual(result["approval"]["status"], "pending")
        response = self.rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "meaning_review", "arguments": {"text": "Review this.", "approval": "rejected", "use_llm": False}}})
        self.assertEqual(response["result"]["structuredContent"]["approval"]["status"], "rejected")
        self.assertFalse(response["result"]["structuredContent"]["execution"]["performed"])

    def test_unknown_resource_tool_and_traversal_rejected(self):
        for request in (
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "file:///etc/passwd"}},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "meaning://skills/../../etc/passwd"}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "execute", "arguments": {"command": "calc"}}},
        ):
            with self.subTest(request=request):
                self.assertIn("error", self.rpc(request))

    def test_invalid_params_and_notifications(self):
        response = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "meaning_analyze", "arguments": {"text": ""}}})
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIsNone(handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        status, headers, _ = self.request(self.port, "GET", "/mcp")
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "POST")

    def test_parse_error_and_host_guard(self):
        status, _, body = self.request(self.port, "POST", "/mcp", b"{", {"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], -32700)
        status, _, _ = self.request(self.port, "POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"Host": "evil.example", "Content-Type": "application/json"})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
