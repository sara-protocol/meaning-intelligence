import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args, input_text=None, env=None):
        process_env = dict(os.environ)
        process_env["PYTHONIOENCODING"] = "utf-8"
        if env:
            process_env.update(env)
        return subprocess.run(
            [sys.executable, "-m", "meaning_agent", *args], cwd=ROOT,
            input=input_text, text=True, encoding="utf-8", capture_output=True,
            env=process_env, timeout=30,
        )

    def test_analyze_json_is_bilingual(self):
        result = self.run_cli("analyze", "--text", "研究显示信任提升，但无来源。是否暂停？", "--offline", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["language"], "zh+en")
        self.assertEqual(list(payload["skills"]), [f"L{i}" for i in range(1, 7)])
        self.assertEqual(payload["approval"]["status"], "pending")
        self.assertTrue(payload["summary"]["en"])

    def test_analyze_markdown(self):
        result = self.run_cli("analyze", "--text", "A claim needs evidence.", "--offline")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Meaning Intelligence", result.stdout)
        self.assertIn("L1", result.stdout)
        self.assertIn("人类", result.stdout)

    def test_review_text_json(self):
        result = self.run_cli("review", "--text", "个人关注自主，组织关注成本。", "--approval", "approved", "--offline", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "meaning_review")
        self.assertEqual(payload["approval"]["status"], "approved")
        self.assertFalse(payload["execution"]["performed"])

    def test_demo_json(self):
        result = self.run_cli("demo", "--offline", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["kind"], "meaning_demo")

    def test_mcp_stdio_initialize_and_tools(self):
        requests = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        ]) + "\n"
        result = self.run_cli("mcp", "--transport", "stdio", input_text=requests)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual([tool["name"] for tool in lines[1]["result"]["tools"]], ["meaning_analyze", "meaning_review"])
        self.assertEqual(result.stderr, "")

    def test_http_transport_uses_hardened_core(self):
        from meaning_agent import cli

        with mock.patch("meaning_agent.cli.serve_core") as serve_core:
            self.assertEqual(cli.main(["mcp", "--transport", "http", "--port", "8767"]), 0)
        serve_core.assert_called_once_with(port=8767)

    def test_invalid_input_is_sanitized(self):
        result = self.run_cli("analyze", "--text", "", "--offline", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("sensitive details", result.stderr)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
