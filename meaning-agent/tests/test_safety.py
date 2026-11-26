import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from meaning_agent.safety import (
    MAX_TEXT_CHARS,
    error_category,
    prepare_text,
    redact_text,
    safe_error,
    sanitize_context,
    strict_json_loads,
    valid_local_host,
    validate_llm_base_url,
)


class SafetyTests(unittest.TestCase):
    def test_redacts_environment_key_and_patterns(self):
        secret = "sk-test-SECRET123456"
        with patch.dict(os.environ, {"MI_LLM_API_KEY": secret}):
            text = redact_text(f"{secret} Bearer abc.def.ghi api_key=other-secret")
        self.assertNotIn(secret, text)
        self.assertNotIn("abc.def.ghi", text)
        self.assertNotIn("other-secret", text)
        self.assertIn("[REDACTED]", text)

    def test_redacts_url_credentials(self):
        self.assertNotIn("password", redact_text("https://user:password@example.com/v1"))

    def test_context_redaction_depth_and_nonfinite(self):
        context = {"api_key": "secret", "nested": {"Authorization": "Bearer secret"}, "items": [float("nan")]}
        result = sanitize_context(context)
        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["nested"]["Authorization"], "[REDACTED]")
        self.assertIsNone(result["items"][0])
        deep = "leaf"
        for _ in range(8):
            deep = {"next": deep}
        self.assertIn("TRUNCATED", json.dumps(sanitize_context(deep)))

    def test_prepare_text_truncates_and_records_metadata(self):
        text, metadata = prepare_text("x" * (MAX_TEXT_CHARS + 10))
        self.assertEqual(len(text), MAX_TEXT_CHARS)
        self.assertTrue(metadata["truncated"])
        self.assertEqual(metadata["limit"], MAX_TEXT_CHARS)

    def test_prepare_text_rejects_non_string(self):
        with self.assertRaises(ValueError):
            prepare_text(None)

    def test_strict_json_rejects_duplicates_and_constants(self):
        with self.assertRaises(ValueError):
            strict_json_loads('{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            strict_json_loads('{"a":NaN}')
        self.assertEqual(strict_json_loads('{"a":1}'), {"a": 1})

    def test_llm_url_validation(self):
        self.assertEqual(validate_llm_base_url("http://localhost:1234/v1/"), "http://localhost:1234/v1")
        self.assertEqual(validate_llm_base_url("https://example.com/v1"), "https://example.com/v1")
        for value in ("http://example.com/v1", "https://user:pass@example.com", "ftp://example.com", "https://example.com?key=x", "http://0.0.0.0:1234"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_llm_base_url(value)

    def test_local_host_validation(self):
        self.assertTrue(valid_local_host("127.0.0.1:8766", 8766))
        self.assertTrue(valid_local_host("localhost:8766", 8766))
        self.assertFalse(valid_local_host("example.com:8766", 8766))
        self.assertFalse(valid_local_host("127.0.0.1:9999", 8766))
        self.assertFalse(valid_local_host("bad:port", 8766))

    def test_sanitized_errors_never_include_exception_text(self):
        secret = "sk-test-SECRET123456"
        errors = [
            TimeoutError(secret),
            URLError(secret),
            HTTPError("https://example.com", 500, secret, {}, None),
            ValueError(secret),
            RuntimeError(secret),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                payload = json.dumps(safe_error(error))
                self.assertNotIn(secret, payload)
                self.assertIn("message", payload)

    def test_error_categories(self):
        self.assertEqual(error_category(TimeoutError()), "timeout")
        self.assertEqual(error_category(URLError("x")), "upstream_connection_error")
        self.assertEqual(error_category(ValueError("x")), "invalid_response")


if __name__ == "__main__":
    unittest.main()
