from __future__ import annotations

import contextlib
import copy
import http.client
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import unittest
from unittest import mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meaning_agent import analyze, demo, registry_metadata, review, to_markdown
from meaning_agent.constants import D7_MODULES, EVIDENCE_LEVELS, HYPOTHESES, SCHEMA_VERSION, SKILL_NAMES
from meaning_agent.llm import LLMConfig, NoRedirect, assist, request_json, validate_enhancement
from meaning_agent.safety import strict_json_loads, validate_llm_base_url
from meaning_agent.skills.registry import get_skill, run_skill
from meaning_agent.web import create_server


def clean_env():
    env = os.environ.copy()
    for key in ("MI_LLM_BASE_URL", "MI_LLM_API_KEY", "MI_LLM_MODEL", "MI_LLM_TIMEOUT"):
        env.pop(key, None)
    return env


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(server, method, path, body=None, headers=None):
    request_headers = dict(headers or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
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


@contextlib.contextmanager
def running_server():
    server = create_server(free_port())
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class SkillAndAnalysisTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_registry_has_exactly_six_complete_skills(self):
        metadata = registry_metadata()
        self.assertEqual(len(metadata), 6)
        self.assertEqual([item["layer"] for item in metadata], ["L1", "L2", "L3", "L4", "L5", "L6"])
        self.assertEqual(tuple(item["name"] for item in metadata), SKILL_NAMES)
        for item in metadata:
            for field in ("name", "description", "layer", "input", "output"):
                self.assertTrue(item[field])
            self.assertRegex(item["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            spec, runner = get_skill(item["layer"])
            self.assertEqual(spec.name, item["name"])
            self.assertTrue(callable(runner))

    def test_analyze_is_offline_deterministic_and_serializable(self):
        text = "研究显示效率提升，但来源缺失。是否应该保留自主？"
        first = analyze(text)
        second = analyze(text)
        self.assertEqual(first["mode"], "offline")
        self.assertEqual(first["schema_version"], SCHEMA_VERSION)
        self.assertEqual(list(first["skills"]), ["L1", "L2", "L3", "L4", "L5", "L6"])
        self.assertEqual(first["skills"], second["skills"])
        json.dumps(first, ensure_ascii=False, allow_nan=False)
        self.assertIn("# Meaning Intelligence", first["markdown"])
        self.assertIn("E0–E6", first["markdown"])

    def test_l1_separates_questions_and_unverified_statements(self):
        result = run_skill("L1", {"text": "研究显示效率提升。是否应该暂停？必须设置预算边界。"})
        data = result["data"]
        statements = data["fact_question_separation"]["reported_statements"]
        questions = data["fact_question_separation"]["open_questions"]
        self.assertEqual(len(statements), 2)
        self.assertEqual(len(questions), 1)
        self.assertIn("是否", questions[0]["text"])
        self.assertTrue(all(item["verification"] == "unverified" for item in statements))
        self.assertTrue(all(item["empirical_status"] == "unknown" for item in statements))
        self.assertTrue(data["critical_constraints"])
        self.assertFalse(data["key_structure"]["causality_inferred"])
        self.assertTrue(all(edge["inferred_causality"] is False for edge in data["key_structure"]["relations"]))

    def test_l2_returns_escaped_interactive_offline_html(self):
        result = run_skill("L2", {
            "text": "信任与自主需要边界。",
            "context": {"title": "<script>alert(1)</script>"},
            "upstream": {"L1": run_skill("L1", {"text": "信任与自主需要边界。"})},
        })
        data = result["data"]
        fragment = data["interactive_html"]
        self.assertIn('type="range"', fragment)
        self.assertIn("addEventListener", fragment)
        self.assertNotIn("<script>alert(1)</script>", fragment)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", fragment)
        self.assertFalse(data["html_safety"]["network"])
        self.assertEqual(data["html_safety"]["execution"], "local_display_only")
        self.assertNotIn("fetch(", fragment)
        self.assertNotIn("XMLHttpRequest", fragment)
        self.assertTrue(any(item["name"] == "detail_level" and item["implemented"] for item in data["parameter_suggestions"]))

    def test_l3_extracts_three_dimensions_and_continuous_spectrum(self):
        result = run_skill("L3", {
            "text": "我们应该提升效率，同时保留自主；预算期限为三个月。",
            "context": {
                "direction": "受控提升协作效率",
                "value_types": ["utility", "intrinsic"],
                "boundaries": {"temporal": "三个月", "spatial": "试点团队", "relational": "成员与用户"},
                "spectrum_position": 42,
            },
        })
        data = result["data"]
        self.assertEqual(set(data["dimensions"]), {"direction", "value", "boundary"})
        self.assertEqual(data["dimensions"]["direction"]["statement"], "受控提升协作效率")
        self.assertEqual({item["type"] for item in data["dimensions"]["value"]["candidates"]}, {"utility", "intrinsic"})
        self.assertEqual(data["dimensions"]["boundary"]["temporal"], "三个月")
        self.assertEqual(data["spectrum"]["position"], 42)
        self.assertFalse(data["spectrum"]["fixed_three_drawers"])
        self.assertTrue(data["spectrum"]["not_the_four_dimension_bs_model"])

    def test_l3_missing_information_requests_clarification(self):
        result = run_skill("L3", {"text": "一个想法。", "context": {"value_types": None}})
        self.assertEqual(result["status"], "needs_clarification")
        codes = {item["code"] for item in result["needs_clarification"]}
        self.assertTrue({"direction_missing", "value_missing", "spectrum_missing"} <= codes)
        self.assertIsNone(result["data"]["dimensions"]["direction"]["statement"])

    def test_l4_preserves_evidence_boundaries_and_canon_records(self):
        result = run_skill("L4", {
            "text": "研究显示信任提升。",
            "context": {"evidence": [{"source": "用户材料", "description": "未核验", "level": "E4"}]},
            "upstream": {"L3": run_skill("L3", {"text": "研究显示信任提升。"})},
        })
        data = result["data"]
        self.assertEqual([item["id"] for item in data["reference_scale"]], [item["id"] for item in EVIDENCE_LEVELS])
        self.assertIsNone(data["automatic_empirical_level"])
        self.assertFalse(data["automatic_empirical_level_claim"])
        self.assertEqual(data["evidence_items"][0]["claimed_level"], "E4")
        self.assertIsNone(data["evidence_items"][0]["accepted_level"])
        self.assertTrue(all(item["empirical_level"] is None for item in data["claims"]))
        self.assertEqual({item["id"] for item in data["canon_hypotheses"]}, {item["id"] for item in HYPOTHESES})
        self.assertEqual({item["id"] for item in data["appendix_d7"]}, {item["id"] for item in D7_MODULES})
        self.assertTrue(all(item["requires_preregistration"] and not item["formal_disposition_allowed"] for item in data["falsification_conditions"]["engineering_drafts"]))
        self.assertEqual(result["status"], "needs_clarification")

    def test_l5_calibrates_explicit_scales_without_weighted_summation(self):
        result = run_skill("L5", {
            "text": "个人与组织存在冲突。",
            "scales": ["individual", "organization"],
            "context": {
                "preferred_direction": "受控协作",
                "scale_positions": {
                    "individual": {"direction": "保留自主", "alignment": "conflict", "costs": ["选择成本"]},
                    "organization": {"direction": "提升效率", "costs": ["预算"]},
                },
                "scale_priorities": ["individual", "organization"],
                "expires_on": "2027-01-01",
                "triggers": ["预算超限"],
            },
            "upstream": {"L3": run_skill("L3", {"text": "个人与组织存在冲突。"})},
        })
        data = result["data"]
        self.assertEqual(data["scales_requested"], ["individual", "organization"])
        self.assertEqual(len(data["scale_positions"]), 2)
        self.assertTrue(data["conflicts"])
        self.assertEqual(data["priority_order"], ["individual", "organization"])
        self.assertEqual(data["aggregation"]["method"], "recursive_calibration")
        self.assertFalse(data["aggregation"]["weighted_sum"])
        self.assertIsNone(data["aggregation"]["weighted_total"])
        self.assertEqual(data["provisional_direction"]["human_approval"], "pending")
        self.assertFalse(data["automatic_execution"])

    def test_l5_missing_positions_priorities_costs_and_expiry_are_not_invented(self):
        result = run_skill("L5", {"text": "需要选择一个方向。", "scales": ["个人"]})
        self.assertEqual(result["status"], "needs_clarification")
        codes = {item["code"] for item in result["needs_clarification"]}
        self.assertTrue({"scale_positions_missing", "priority_missing", "costs_missing", "expiry_missing"} <= codes)
        self.assertIsNone(result["data"]["scale_positions"][0]["direction"])

    def test_l6_feedback_zeroing_and_professional_review(self):
        previous = analyze("个人希望保留自主，组织担心成本。")
        evidence = run_skill("L6", {"text": previous["input"]["text"], "analysis": previous, "feedback": "请复核证据来源"})
        self.assertTrue(evidence["data"]["revision_required"])
        self.assertIn("feedback_evidence", {item["code"] for item in evidence["data"]["review_triggers"]})
        zero = run_skill("L6", {"text": previous["input"]["text"], "analysis": previous, "feedback": "请主动归零"})
        self.assertTrue(zero["data"]["zeroing_plan"]["recommended"])
        self.assertEqual(zero["data"]["zeroing_plan"]["mode"], "controlled_reset")
        medical = analyze("患者询问诊断和用药，是否应该自行治疗？")
        self.assertIn("professional_review_required", {item["code"] for item in medical["skills"]["L6"]["data"]["review_triggers"]})
        self.assertEqual(medical["skills"]["L6"]["data"]["approval_gate"]["required_professional_domains"], ["medical"])

    def test_approval_defaults_to_pending_and_never_authorizes_execution(self):
        result = analyze("组织应该提升效率。")
        self.assertEqual(result["approval_gate"]["status"], "pending")
        self.assertTrue(result["approval_gate"]["human_required"])
        self.assertFalse(result["approval_gate"]["execution_authorized"])
        self.assertEqual(result["skills"]["L5"]["data"]["provisional_direction"]["status"], "provisional_pending_human_approval")

    def test_invalid_inputs_and_missing_skill_text_request_clarification(self):
        with self.assertRaises(ValueError):
            analyze("")
        with self.assertRaises(ValueError):
            analyze("文本", context=[])
        with self.assertRaises(ValueError):
            analyze("文本", scales="individual")
        missing = run_skill("L3", {"text": ""})
        self.assertEqual(missing["status"], "needs_clarification")
        self.assertTrue(missing["needs_clarification"])

    def test_review_reruns_l6_and_does_not_mutate_previous(self):
        previous = analyze("个人希望保留自主，组织担心成本。")
        snapshot = copy.deepcopy(previous)
        revised = review(previous, "证据错误，请复核来源")
        self.assertTrue(revised["revision_required"])
        self.assertIn("L4", revised["affected_skills"])
        self.assertEqual(revised["approval_gate"]["status"], "pending")
        self.assertEqual(previous, snapshot)
        self.assertEqual(revised["review"]["layer"], "L6")

    def test_replace_text_reanalyzes_and_resets_invalidated_approval(self):
        previous = analyze("旧方向。")
        previous["approval"] = {**previous["approval"], "status": "approved"}
        previous["approval_gate"] = {**previous["approval_gate"], "status": "approved"}
        revised = review(previous, {"action": "replace_text", "text": "新方向应该保留自主。"})
        self.assertTrue(revised["revision_required"])
        self.assertEqual(revised["revised_analysis"]["input"]["text"], "新方向应该保留自主。")
        self.assertEqual(revised["revised_analysis"]["approval_gate"]["status"], "pending")
        self.assertEqual(previous["approval_gate"]["status"], "approved")
        self.assertIn("feedback_correction", {item["code"] for item in revised["review"]["data"]["review_triggers"]})

    def test_demo_supports_markdown_and_json(self):
        self.assertIsInstance(demo(), str)
        value = demo(as_json=True)
        self.assertEqual(value["kind"], "meaning_demo")
        self.assertEqual(value["analysis"]["mode"], "offline")
        self.assertIn("markdown", value)

    def test_secrets_are_redacted_from_text_context_and_markdown(self):
        secret = "sk-ABCDEFGHIJK123456789"
        with mock.patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            result = analyze(f"api_key={secret}；请分析。", context={"token": secret, "note": f"Bearer {secret}"}, use_llm=False)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(secret, result["markdown"])
        self.assertIn("[REDACTED]", serialized)

    def test_long_text_is_truncated_with_metadata(self):
        result = analyze("甲" * 20050, use_llm=False)
        self.assertTrue(result["input"]["text_metadata"]["truncated"])
        self.assertEqual(result["input"]["text_metadata"]["analyzed_characters"], 20000)


class LLMTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_configuration_requires_key_and_reads_only_documented_variables(self):
        with mock.patch.dict(os.environ, {"MI_LLM_BASE_URL": "https://example.test/v1", "MI_LLM_MODEL": "model"}):
            self.assertIsNone(LLMConfig.from_env())
        with mock.patch.dict(os.environ, {
            "MI_LLM_BASE_URL": "https://example.test/v1",
            "MI_LLM_MODEL": "model",
            "MI_LLM_API_KEY": "secret-value",
            "MI_LLM_TIMEOUT": "not-a-number",
        }):
            config = LLMConfig.from_env()
            self.assertEqual(config.timeout, 15.0)
            self.assertNotIn("secret-value", repr(config))

    def test_base_url_rejects_credentials_query_and_remote_http(self):
        for value in (
            "https://user:pass@example.test/v1",
            "https://example.test/v1?key=value",
            "http://example.test/v1",
            "file:///tmp/model",
            "https://0.0.0.0/v1",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_llm_base_url(value)
        self.assertEqual(validate_llm_base_url("http://127.0.0.1:11434/v1"), "http://127.0.0.1:11434/v1")

    def test_strict_json_rejects_duplicates_and_non_finite_numbers(self):
        with self.assertRaises(ValueError):
            strict_json_loads('{"a": 1, "a": 2}')
        with self.assertRaises(ValueError):
            strict_json_loads('{"a": NaN}')

    def test_llm_output_allowlist_and_redaction(self):
        secret = "sk-ABCDEFGHIJK123456789"
        with mock.patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            value = validate_enhancement({"summary_zh": f"key={secret}", "questions_en": ["缺少来源"]})
        self.assertNotIn(secret, value["summary_zh"])
        self.assertEqual(value["questions_en"], ["缺少来源"])
        with self.assertRaises(ValueError):
            validate_enhancement({"approval": "approved"})
        with self.assertRaises(ValueError):
            validate_enhancement({"summary_zh": 123})

    def test_request_uses_header_only_key_timeout_and_strict_content(self):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                payload = {"choices": [{"message": {"content": '{"summary_zh":"候选摘要"}'}}]}
                return json.dumps(payload).encode("utf-8")

        class Opener:
            def open(self, req, timeout):
                captured["request"] = req
                captured["timeout"] = timeout
                return Response()

        config = LLMConfig("https://example.test/v1", "model", "header-secret", timeout=15.0)
        with mock.patch("meaning_agent.llm.build_opener", return_value=Opener()):
            result = request_json(config, "system", {"text": "input"})
        self.assertEqual(result, {"summary_zh": "候选摘要"})
        self.assertEqual(captured["timeout"], 15.0)
        self.assertEqual(captured["request"].get_header("Authorization"), "Bearer header-secret")
        self.assertNotIn(b"header-secret", captured["request"].data)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "found", {}, "https://other.test"))

    def test_llm_failure_falls_back_without_secret_details(self):
        secret = "sk-ABCDEFGHIJK123456789"
        with mock.patch.dict(os.environ, {
            "MI_LLM_BASE_URL": "https://example.test/v1",
            "MI_LLM_MODEL": "model",
            "MI_LLM_API_KEY": secret,
        }), mock.patch("meaning_agent.llm.request_json", side_effect=RuntimeError(secret)):
            result = analyze("请分析。", use_llm=True)
        self.assertEqual(result["mode"], "offline_fallback")
        self.assertEqual(result["llm_assistance"]["status"], "error")
        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))
        self.assertFalse(result["llm_assistance"]["error"]["message"]["zh"].find(secret) >= 0)

    def test_llm_success_changes_mode_but_not_authoritative_skills(self):
        baseline = analyze("请分析。", use_llm=False)
        suggestion = {
            "status": "ok", "error": None,
            "output": {"summary_zh": "未核验摘要", "summary_en": "Unverified summary"},
        }
        with mock.patch("meaning_agent.engine.assist", return_value=suggestion):
            enhanced = analyze("请分析。", use_llm=True)
        self.assertEqual(enhanced["mode"], "llm")
        self.assertEqual(enhanced["skills"], baseline["skills"])
        self.assertEqual(enhanced["approval_gate"]["status"], "pending")


class WebTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_server_rejects_non_loopback_binding(self):
        with self.assertRaises(ValueError):
            create_server(8766, host="0.0.0.0")

    def test_index_static_assets_health_and_meta(self):
        with running_server() as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            status, index, headers = request(server, "GET", "/")
            self.assertEqual(status, 200)
            self.assertIn(b"Meaning Agent", index)
            self.assertIn("script-src 'self'", headers["content-security-policy"])
            self.assertEqual(request(server, "GET", "/static/app.js")[0], 200)
            self.assertEqual(request(server, "GET", "/static/styles.css")[0], 200)
            health = request(server, "GET", "/health")[1]
            self.assertEqual(health["bind"], "127.0.0.1")
            self.assertFalse(health["arbitrary_file_or_command_api"])
            meta = request(server, "GET", "/api/meta")[1]
            self.assertEqual(len(meta["skills"]), 6)
            self.assertEqual(len(meta["scales"]), 5)

    def test_analyze_and_review_api(self):
        with running_server() as server:
            status, result, _ = request(server, "POST", "/api/analyze", body={"text": "个人与组织存在冲突。", "scales": ["individual", "organization"]})
            self.assertEqual(status, 200)
            self.assertEqual(result["mode"], "offline")
            status, revised, _ = request(server, "POST", "/api/review", body={"previous": result, "feedback": "请复核证据来源"})
            self.assertEqual(status, 200)
            self.assertTrue(revised["revision_required"])

    def test_origin_host_traversal_and_invalid_json_are_rejected(self):
        with running_server() as server:
            self.assertEqual(request(server, "GET", "/", headers={"Host": "evil.example"})[0], 403)
            self.assertEqual(request(server, "POST", "/api/analyze", body={"text": "文本"}, headers={"Origin": "https://evil.example"})[0], 403)
            self.assertEqual(request(server, "GET", "/%2e%2e/%2e%2e/etc/passwd")[0], 404)
            self.assertEqual(request(server, "GET", "/static/%2e%2e/%2e%2e/README.md")[0], 404)
            self.assertEqual(request(server, "POST", "/api/analyze", body=b"{broken", headers={"Content-Type": "application/json"})[0], 400)
            self.assertEqual(request(server, "POST", "/api/analyze", body={"text": "文本", "path": "/etc/passwd"})[0], 400)

    def test_web_errors_and_logs_do_not_expose_secrets(self):
        secret = "sk-ABCDEFGHIJK123456789"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"MI_LLM_API_KEY": secret}), running_server() as server:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                response = request(server, "POST", "/api/analyze", body={"text": f"api_key={secret}"})
        self.assertEqual(response[0], 200)
        self.assertNotIn(secret, json.dumps(response[1], ensure_ascii=False))
        self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())


class CLITests(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, "-m", "meaning_agent", *args],
            cwd=ROOT,
            env=clean_env(),
            input=input_text,
            encoding="utf-8",
            errors="strict",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )

    def test_analyze_demo_and_review_commands(self):
        analyzed = self.run_cli("analyze", "--text", "是否应该保留自主？", "--json")
        self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
        result = json.loads(analyzed.stdout)
        self.assertEqual(result["mode"], "offline")
        demo_result = self.run_cli("demo", "--json")
        self.assertEqual(demo_result.returncode, 0, demo_result.stderr)
        self.assertEqual(json.loads(demo_result.stdout)["kind"], "meaning_demo")
        reviewed = self.run_cli("review", "--previous-stdin", "--feedback", "请复核证据来源", "--json", input_text=analyzed.stdout)
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertTrue(json.loads(reviewed.stdout)["revision_required"])

    def test_cli_invalid_input_is_sanitized(self):
        secret = "sk-ABCDEFGHIJK123456789"
        completed = self.run_cli("analyze", "--text", "", "--json")
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn(secret, completed.stdout + completed.stderr)

    def test_frontend_javascript_syntax(self):
        completed = subprocess.run(
            ["node", "--check", str(ROOT / "meaning_agent" / "static" / "app.js")],
            cwd=ROOT,
            env=clean_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class PackagingTests(unittest.TestCase):
    def test_six_skill_documents_have_valid_frontmatter_and_bounds(self):
        files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(files), 6)
        names = set()
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            _, frontmatter, body = text.split("---", 2)
            fields = {}
            for line in frontmatter.strip().splitlines():
                if line.strip():
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            self.assertLess(len(fields["description"]), 1024)
            self.assertIn("Use", fields["description"])
            self.assertLess(len(body.split()), 500)
            self.assertIn("Runner:", body)
            self.assertIn("Output:", body)
            self.assertIn("Limits", body)
            names.add(fields["name"])
        self.assertEqual(names, set(SKILL_NAMES))

    def test_readme_contains_required_operational_and_provenance_sections(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for term in ("快速开始", "Python API", "CLI", "架构与六技能", "安全边界", "正典与白皮书映射", "局限", "127.0.0.1", "MI_LLM_API_KEY", "H1–H18", "附录 D.7"):
            self.assertIn(term, text)

    def test_python_sources_have_no_todo_markers(self):
        for path in (ROOT / "meaning_agent").rglob("*.py"):
            self.assertNotIn("TODO", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
