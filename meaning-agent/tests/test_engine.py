import json
import os
import unittest
from unittest.mock import patch

from meaning_agent import analyze, demo, review, to_markdown
from meaning_agent.constants import SKILL_NAMES
from meaning_agent.safety import MAX_TEXT_CHARS

TEXT = "研究显示新系统提升信任，但没有来源。个人希望自主，组织担心成本，城市关注公平。如果预算超过100万必须暂停。是否应该扩大？"


class EngineTests(unittest.TestCase):
    def test_six_layers_bilingual_and_pending(self):
        result = analyze(TEXT, use_llm=False)
        self.assertEqual(list(result["skills"]), [f"L{i}" for i in range(1, 7)])
        self.assertEqual(result["language"], "zh+en")
        self.assertEqual(result["mode"], "offline")
        self.assertEqual(result["status"], "pending_human_approval")
        self.assertEqual(result["approval"]["status"], "pending")
        self.assertFalse(result["approval"]["execution_authorized"])
        self.assertTrue(result["summary"]["zh"])
        self.assertTrue(result["summary"]["en"])
        self.assertEqual({item["name"] for item in result["skill_list"]}, set(SKILL_NAMES))
        self.assertIn("L1", result["markdown"])
        self.assertIn("Approval", result["markdown"])

    def test_deterministic_output(self):
        first = analyze(TEXT, use_llm=False)
        second = analyze(TEXT, use_llm=False)
        self.assertEqual(first, second)

    def test_no_scale_scores_or_weighted_totals(self):
        result = analyze(TEXT, use_llm=False)
        l5 = result["skills"]["L5"]["data"]
        self.assertEqual(l5["aggregation"]["weighted_summation"], "forbidden")
        self.assertIsNone(l5["aggregation"]["numeric_total"])
        self.assertTrue(all(row["score"] is None for row in l5["scale_calibration"]))
        self.assertFalse(l5["aggregation"]["weighted_sum"])
        self.assertIsNone(l5["aggregation"]["weighted_total"])
        serialized = json.dumps(result)
        self.assertNotIn('"total_score"', serialized)

    def test_evidence_unknown_and_plans_not_tested(self):
        result = analyze(TEXT, use_llm=False)
        l4 = result["skills"]["L4"]["data"]
        self.assertTrue(l4["claim_assessments"])
        for item in l4["claim_assessments"]:
            self.assertFalse(item["independently_verified_by_this_tool"])
        self.assertTrue(all(item["status"] == "not_tested" and item["result"] is None for item in l4["falsification_plans"]))

    def test_review_defaults_pending_and_never_executes(self):
        result = review(TEXT, use_llm=False)
        self.assertEqual(result["approval"]["status"], "pending")
        self.assertFalse(result["execution"]["performed"])
        self.assertEqual(len(result["review"]["data"]["review_passes"]), 3)
        self.assertTrue(result["review"]["data"]["zeroing_protocol"]["reversible"])

    def test_explicit_approval_is_record_only(self):
        result = review(TEXT, approval="approved", use_llm=False)
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertFalse(result["approval"]["execution_authorized"])
        self.assertFalse(result["execution"]["performed"])
        with self.assertRaises(ValueError):
            review(TEXT, approval="automatic", use_llm=False)

    def test_legacy_feedback_review(self):
        previous = analyze(TEXT, use_llm=False)
        result = review(previous, "请补充来源。")
        self.assertEqual(result["feedback"]["text"], "请补充来源。")
        self.assertEqual(result["approval"]["status"], "pending")
        self.assertIn("revised_analysis", result)

    def test_input_validation_and_truncation(self):
        for value in ("", "   ", None, 3):
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(value, use_llm=False)
        with self.assertRaises(ValueError):
            analyze(TEXT, context=[], use_llm=False)
        result = analyze("x" * (MAX_TEXT_CHARS + 100), use_llm=False)
        self.assertTrue(result["input"]["text_metadata"]["truncated"])
        self.assertEqual(len(result["input"]["text"]), MAX_TEXT_CHARS)

    def test_secret_redaction_in_all_output(self):
        secret = "sk-test-SECRET123456"
        with patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            result = analyze(f"api_key={secret}。研究显示效果。", use_llm=False)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_demo_json_and_markdown(self):
        result = demo(as_json=True, use_llm=False)
        self.assertEqual(result["kind"], "meaning_demo")
        self.assertIn("analysis", result)
        markdown = demo(use_llm=False)
        self.assertIn("Meaning Intelligence", markdown)
        self.assertIn("L6", markdown)

    def test_markdown_escapes_html(self):
        result = analyze("<script>alert(1)</script> 是未核实断言。", use_llm=False)
        self.assertNotIn("<script>", result["markdown"])
        self.assertIn("&lt;script&gt;", result["markdown"])


if __name__ == "__main__":
    unittest.main()
