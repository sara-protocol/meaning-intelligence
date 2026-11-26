import unittest

from meaning_agent.skills.registry import SKILLS, registry_metadata, run_skill


class SkillTests(unittest.TestCase):
    def test_registry_has_six_unique_bilingual_skills(self):
        metadata = registry_metadata()
        self.assertEqual(len(metadata), 6)
        self.assertEqual(len({item["name"] for item in metadata}), 6)
        self.assertEqual([item["layer"] for item in metadata], [f"L{i}" for i in range(1, 7)])
        for item in metadata:
            self.assertTrue(item["description"])
            self.assertTrue(item["description_en"])

    def test_every_skill_requests_missing_text_bilingually(self):
        for spec, _ in SKILLS:
            with self.subTest(layer=spec.layer):
                result = run_skill(spec.name, {})
                self.assertEqual(result["status"], "needs_clarification")
                question = result["needs_clarification"][0]
                self.assertIn("zh", question)
                self.assertIn("en", question)

    def test_l1_separates_questions_and_never_verifies(self):
        result = run_skill("L1", {"text": "研究显示信任提升。是否应该暂停？必须保留数据删除权。"})
        data = result["data"]
        statements = data["fact_question_separation"]["reported_statements"]
        questions = data["fact_question_separation"]["open_questions"]
        self.assertEqual(len(statements), 2)
        self.assertEqual(len(questions), 1)
        self.assertTrue(all(item["verification"] == "unverified" for item in statements))
        self.assertTrue(all(item["empirical_status"] == "unknown" for item in statements))
        self.assertEqual(data["critical_constraints"], ["必须保留数据删除权。"])
        self.assertTrue(all(not edge["inferred_causality"] for edge in data["key_structure"]["relations"]))
        self.assertIn("研究显示", data["source_text"])

    def test_l1_english_question(self):
        result = run_skill("L1", {"text": "A study reports higher trust. Should we pause? The budget must not increase."})
        data = result["data"]
        self.assertEqual(len(data["fact_question_separation"]["open_questions"]), 1)
        self.assertEqual(data["controlled_restatement"]["language"], "en")
        self.assertTrue(data["critical_constraints"])

    def test_l2_parameters_and_safe_interactive_html(self):
        upstream = {"L1": {"data": {"key_structure": {"nodes": [{"label": "<script>", "mentions": 1}]}, "fact_question_separation": {"open_questions": [{"text": "<img src=x>"}]}}}}
        result = run_skill("L2", {"text": "人类批准和即时反馈很重要。", "upstream": upstream})
        data = result["data"]
        self.assertEqual({item["id"] for item in data["parameters"]}, {"cognitive_load", "agency", "feedback_timing", "pace", "reversibility"})
        safe_html = data["safe_html_suggestion"]
        interactive_html = data["interactive_html"]
        self.assertNotIn("<script", safe_html.lower())
        self.assertIn("addEventListener", interactive_html)
        self.assertNotIn("<script>alert", interactive_html.lower())
        self.assertNotIn("<img", interactive_html.lower())
        self.assertNotIn("onclick", interactive_html.lower())
        self.assertNotIn("http://", interactive_html.lower())
        self.assertIn("&lt;script&gt;", interactive_html)
        self.assertFalse(data["html_safety"]["network"])
        self.assertTrue(data["html_safety"]["interactive_html_scripts"])
        self.assertEqual(data["html_safety"]["execution"], "local_display_only")
        self.assertTrue(any(item["name"] == "detail_level" and item["implemented"] for item in data["parameter_suggestions"]))
        self.assertTrue(data["experience_is_not_validation"])

    def test_l3_candidates_spectrum_and_human_choice(self):
        result = run_skill("L3", {"text": "应提升公平并减少风险。不得越过预算边界。"})
        data = result["data"]
        self.assertTrue(data["directions"])
        self.assertTrue(data["values"])
        self.assertTrue(data["boundaries"]["hard"])
        spectrum = data["continuous_spectrum"]
        self.assertEqual((spectrum["minimum"], spectrum["maximum"]), (0, 100))
        self.assertFalse(spectrum["position_is_measurement"])
        self.assertIsNone(spectrum["selected_position"])
        self.assertIsNone(data["selected_direction"])
        self.assertEqual(data["approval_status"], "pending_human")

    def test_l3_honors_only_valid_user_position(self):
        good = run_skill("L3", {"text": "保持方向。", "context": {"spectrum_position": 37}})
        bad = run_skill("L3", {"text": "保持方向。", "context": {"spectrum_position": 101}})
        self.assertEqual(good["data"]["continuous_spectrum"]["position_source"], "user_context")
        self.assertEqual(good["data"]["continuous_spectrum"]["heuristic_position"], 37)
        self.assertEqual(bad["data"]["continuous_spectrum"]["position_source"], "no_reliable_cue")
        self.assertIsNone(bad["data"]["continuous_spectrum"]["selected_position"])

    def test_l4_conservative_evidence_and_falsification(self):
        statements = [{"id": "s1", "text": "研究显示效果提升。", "kind": "empirical_claim_unverified"}]
        result = run_skill("L4", {"text": "研究显示效果提升。", "statements": statements})
        data = result["data"]
        assessment = data["claim_assessments"][0]
        self.assertIsNone(assessment["level"])
        self.assertEqual(assessment["level_source"], "not_assigned")
        self.assertEqual(assessment["current_empirical_status"], "unknown")
        self.assertFalse(assessment["independently_verified_by_this_tool"])
        self.assertEqual(data["falsification_plans"][0]["status"], "not_tested")
        self.assertIsNone(data["falsification_plans"][0]["result"])
        self.assertEqual([item["id"] for item in data["evidence_catalog"]], [f"E{i}" for i in range(7)])

    def test_l4_accepts_string_evidence_without_inventing_a_level(self):
        result = run_skill("L4", {"text": "研究显示效果提升。", "context": {"evidence": ["用户提供的报告"]}})
        item = result["data"]["evidence_items"][0]
        self.assertEqual(item["description"], "用户提供的报告")
        self.assertIsNone(item["claimed_level"])
        self.assertIsNone(item["accepted_level"])
        self.assertEqual(item["verification_status"], "user_supplied_unverified")

    def test_l4_uses_supplied_level_without_claiming_verification(self):
        statements = [{"id": "s1", "text": "独立实验室复现该结果。", "kind": "empirical_claim_unverified"}]
        context = {"evidence": [{"claim_id": "s1", "level": "E4", "source": "user supplied", "verified": True}]}
        result = run_skill("L4", {"text": "独立实验室复现该结果。", "statements": statements, "context": context})
        assessment = result["data"]["claim_assessments"][0]
        self.assertEqual(assessment["level"], "E4")
        self.assertTrue(assessment["supplied_metadata_claims_verified"])
        self.assertFalse(assessment["independently_verified_by_this_tool"])
        self.assertEqual(assessment["current_empirical_status"], "user_asserted_not_independently_verified")

    def test_l4_links_canon_as_record_only(self):
        result = run_skill("L4", {"text": "意义不可还原性需要检验。", "statements": []})
        linked = result["data"]["hypothesis_candidates"]
        self.assertEqual(linked[0]["id"], "H2")
        self.assertIn("不是本工具", linked[0]["warning"]["zh"])

    def test_l5_five_scales_no_weighted_sum(self):
        result = run_skill("L5", {"text": "个人重视自主，组织重视成本，城市关注公平。如果预算超限必须暂停。"})
        data = result["data"]
        rows = data["scale_calibration"]
        self.assertEqual([row["scale"] for row in rows], ["individual", "organization", "city", "national", "humanity"])
        self.assertTrue(all(row["score"] is None for row in rows))
        self.assertEqual(data["aggregation"]["weighted_summation"], "forbidden")
        self.assertEqual(data["aggregation"]["compensation"], "forbidden")
        self.assertIsNone(data["aggregation"]["numeric_total"])
        self.assertIsNone(data["selected_priority"])
        self.assertTrue(data["triggers"])

    def test_l6_bounded_review_and_reversible_zeroing(self):
        l1 = run_skill("L1", {"text": "研究显示效果提升，但无来源。"})
        l4 = run_skill("L4", {"text": "研究显示效果提升，但无来源。", "statements": l1["data"]["fact_question_separation"]["reported_statements"]})
        l5 = run_skill("L5", {"text": "研究显示效果提升，但无来源。"})
        pipeline_input = {"L1": l1, "L4": l4, "L5": l5}
        result = run_skill("L6", {"text": "研究显示效果提升，但无来源。", "analysis": {"skills": pipeline_input}})
        data = result["data"]
        self.assertEqual(len(data["review_passes"]), 3)
        self.assertTrue(all(item["stop_reason"] == "max_three_passes" for item in data["review_passes"]))
        self.assertTrue(data["zeroing_protocol"]["reversible"])
        self.assertFalse(data["zeroing_protocol"]["data_deleted"])
        self.assertFalse(data["zeroing_protocol"]["execution_allowed"])
        self.assertEqual(data["approval_status"], "pending_human")


if __name__ == "__main__":
    unittest.main()
