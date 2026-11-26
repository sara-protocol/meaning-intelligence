import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from meaning_agent import llm
from meaning_agent.engine import analyze
from meaning_agent.safety import redact_text


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


class FakeOpener:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if self.error:
            raise self.error
        return FakeResponse(self.body)


def outer(content):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")


class LLMTests(unittest.TestCase):
    def test_config_requires_base_and_model_together(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(llm.LLMConfig.from_env())
        with patch.dict(os.environ, {"MI_LLM_BASE_URL": "http://localhost:1234/v1"}, clear=True):
            with self.assertRaises(ValueError):
                llm.LLMConfig.from_env()

    def test_endpoint_and_key_not_in_repr(self):
        secret = "sk-test-SECRET123456"
        config = llm.LLMConfig("http://localhost:1234/v1", "model", secret, 5)
        self.assertEqual(config.endpoint, "http://localhost:1234/v1/chat/completions")
        self.assertNotIn(secret, repr(config))
        self.assertEqual(llm.LLMConfig("https://example.com", "m").endpoint, "https://example.com/v1/chat/completions")

    def test_request_strict_json_and_authorization_header(self):
        secret = "sk-test-SECRET123456"
        opener = FakeOpener(outer('{"summary_zh":"摘要","summary_en":"Summary"}'))
        config = llm.LLMConfig("http://localhost:1234/v1", "model", secret, 7)
        with patch("meaning_agent.llm.build_opener", return_value=opener):
            result = llm.request_json(config, "system", {"text": "hello"})
        self.assertEqual(result["summary_zh"], "摘要")
        self.assertEqual(opener.timeout, 7)
        headers = {key.lower(): value for key, value in opener.request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer " + secret)
        self.assertNotIn(secret.encode(), opener.request.data)

    def test_markdown_and_duplicate_content_rejected(self):
        config = llm.LLMConfig("http://localhost:1234/v1", "model")
        for content in ('```json\n{"summary_zh":"x"}\n```', '{"summary_zh":"x","summary_zh":"y"}', '[]', '{"summary_zh":NaN}'):
            with self.subTest(content=content):
                opener = FakeOpener(outer(content))
                with patch("meaning_agent.llm.build_opener", return_value=opener), self.assertRaises(ValueError):
                    llm.request_json(config, "system", {})

    def test_oversized_response_rejected(self):
        config = llm.LLMConfig("http://localhost:1234/v1", "model")
        opener = FakeOpener(b"x" * (llm.MAX_RESPONSE_BYTES + 1))
        with patch("meaning_agent.llm.build_opener", return_value=opener), self.assertRaises(ValueError):
            llm.request_json(config, "system", {})

    def test_enhancement_schema_rejects_invalid_question_list(self):
        with self.assertRaises(ValueError):
            llm.validate_enhancement({"summary_zh": "摘要", "questions_en": ["Why?", 3]})


class LLMValidationTests(unittest.TestCase):
    def test_invalid_question_item_rejected(self):
        with self.assertRaises(ValueError):
            llm.validate_enhancement({"questions_en": ["Why?", 3]})

    def test_unexpected_field_rejected(self):
        with self.assertRaises(ValueError):
            llm.validate_enhancement({"evidence_level": "E6"})

    def test_valid_fields_redacted_and_bounded(self):
        secret = "sk-test-SECRET123456"
        with patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            result = llm.validate_enhancement({"summary_zh": secret, "questions_en": ["Why?"]})
        self.assertNotIn(secret, result["summary_zh"])
        self.assertEqual(result["questions_en"], ["Why?"])

    def test_assist_success_and_failure_are_sanitized(self):
        secret = "sk-test-SECRET123456"
        env = {"MI_LLM_BASE_URL": "http://localhost:1234/v1", "MI_LLM_MODEL": "model", "MI_LLM_API_KEY": secret}
        with patch.dict(os.environ, env, clear=True):
            opener = FakeOpener(outer('{"summary_zh":"保留未知","summary_en":"Keep unknown"}'))
            with patch("meaning_agent.llm.build_opener", return_value=opener):
                result = llm.assist("text", {}, {"zh": "d", "en": "d"})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["output"]["summary_en"], "Keep unknown")
            with patch("meaning_agent.llm.build_opener", return_value=FakeOpener(error=URLError(secret))):
                result = analyze("研究显示效果，但未提供来源。", use_llm=True)
        self.assertEqual(result["mode"], "offline_fallback")
        self.assertEqual(result["llm_assistance"]["status"], "error")
        self.assertNotIn(secret, json.dumps(result, ensure_ascii=False))

    def test_offline_never_calls_adapter(self):
        with patch("meaning_agent.llm.request_json", side_effect=AssertionError("must not call")):
            result = analyze("A claim without a source.", use_llm=False)
        self.assertEqual(result["mode"], "offline")
        self.assertEqual(result["llm_assistance"]["status"], "disabled_by_request")

    def test_redact_helper_removes_configured_key(self):
        secret = "sk-test-SECRET123456"
        with patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            self.assertNotIn(secret, redact_text(secret))


if __name__ == "__main__":
    unittest.main()
