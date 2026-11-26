"""Input, output, and transport hardening. No credentials are persisted."""

import json
import math
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

SENSITIVE_KEY = re.compile(r"(?:api[_-]?key|token|secret|password|credential|authorization|cookie)", re.I)
SECRET_PATTERN = re.compile(
    r"(?:\b(?:sk|pk|key)-[A-Za-z0-9_-]{8,}\b|\bBearer\s+[A-Za-z0-9._~+/-]+=*|"
    r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)",
    re.I,
)
URL_CREDENTIALS = re.compile(r"https?://[^\s/@]+:[^\s/@]+@", re.I)
MAX_TEXT_CHARS = 20000
MAX_CONTEXT_STRING = 2000
MAX_BODY_BYTES = 512 * 1024
MAX_JSONRPC_LINE = 512 * 1024


def known_secrets(extra=()):
    values = []
    for name in ("MI_LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        value = os.environ.get(name, "")
        if value:
            values.append(value)
    values.extend(item for item in extra if isinstance(item, str) and item)
    return sorted(set(values), key=len, reverse=True)


def redact_text(value, extra_secrets=()):
    text = str(value)
    for secret in known_secrets(extra_secrets):
        text = text.replace(secret, "[REDACTED]")
    text = URL_CREDENTIALS.sub("[REDACTED_URL_CREDENTIALS]@", text)
    return SECRET_PATTERN.sub("[REDACTED]", text)


def sanitize_context(value, depth=0):
    if depth > 6:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 100:
                result["_truncated"] = True
                break
            key = redact_text(key)[:100]
            if SENSITIVE_KEY.search(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_context(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize_context(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return redact_text(value[:MAX_CONTEXT_STRING])
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return redact_text(value)[:MAX_CONTEXT_STRING]


def prepare_text(value):
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    original_length = len(value)
    text = redact_text(value).strip()
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS]
    return text, {
        "original_characters": original_length,
        "analyzed_characters": len(text),
        "truncated": truncated,
        "limit": MAX_TEXT_CHARS,
        "secrets_redacted": "[REDACTED]" in redact_text(value),
    }


def strict_json_loads(value):
    def pairs_hook(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result

    def bad_constant(_):
        raise ValueError("non-finite JSON number")

    return json.loads(value, object_pairs_hook=pairs_hook, parse_constant=bad_constant)


def validate_llm_base_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("MI_LLM_BASE_URL must be a URL")
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("MI_LLM_BASE_URL must use http(s)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("MI_LLM_BASE_URL cannot contain credentials, query, or fragment")
    host = parsed.hostname.lower()
    if parsed.scheme == "http" and host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("remote LLM URLs must use https")
    if host in ("0.0.0.0", "::"):
        raise ValueError("unspecified LLM hosts are not allowed")
    return value.rstrip("/")


def valid_local_host(value, port):
    if not value:
        return False
    try:
        parsed = urlsplit("//" + value)
        host = (parsed.hostname or "").lower()
        parsed_port = parsed.port or port
    except ValueError:
        return False
    return host in ("127.0.0.1", "localhost", "::1") and parsed_port == port


def safe_error(exc):
    category = error_category(exc)
    if isinstance(exc, HTTPError):
        try:
            exc.close()
        except Exception:
            pass
    messages = {
        "timeout": ("上游模型请求超时；已保留离线结果。", "The upstream model timed out; offline results were retained."),
        "upstream_http_error": ("上游模型返回错误；已保留离线结果。", "The upstream model returned an error; offline results were retained."),
        "upstream_connection_error": ("无法连接上游模型；已保留离线结果。", "Could not connect to the upstream model; offline results were retained."),
        "invalid_response": ("上游响应不是严格 JSON 或不符合约定；已保留离线结果。", "The upstream response was not strict JSON or violated the contract; offline results were retained."),
        "invalid_input": ("输入无效；请检查文本与 JSON 格式。", "Invalid input; check the text and JSON format."),
        "not_found": ("资源不存在。", "Resource not found."),
        "method_not_allowed": ("请求方法不允许。", "Method not allowed."),
        "request_too_large": ("请求体过大。", "Request body is too large."),
        "forbidden": ("请求来源不被允许。", "Request origin is not allowed."),
        "adapter_error": ("模型适配器失败；已保留离线结果。", "The model adapter failed; offline results were retained."),
        "internal_error": ("内部错误；未返回敏感详情。", "Internal error; sensitive details were not returned."),
    }
    zh, en = messages.get(category, messages["internal_error"])
    return {"code": category, "message": {"zh": zh, "en": en}}


def error_category(exc):
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, HTTPError):
        return "upstream_http_error"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        return "timeout" if isinstance(reason, TimeoutError) else "upstream_connection_error"
    if isinstance(exc, (ValueError, UnicodeError, json.JSONDecodeError)):
        return "invalid_response"
    return "adapter_error"
