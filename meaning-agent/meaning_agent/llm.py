"""Optional OpenAI-compatible LLM adapter using only the standard library."""

import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .safety import redact_text, safe_error, strict_json_loads, validate_llm_base_url

MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_FIELDS = ("summary", "clarification_questions", "revision_suggestions", "boundary_reminders")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)
    timeout: float = 15.0

    @classmethod
    def from_env(cls):
        base_url = os.environ.get("MI_LLM_BASE_URL", "").strip()
        model = os.environ.get("MI_LLM_MODEL", "").strip()
        api_key = os.environ.get("MI_LLM_API_KEY", "").strip()
        if not base_url and not model and not api_key:
            return None
        if not base_url or not model:
            raise ValueError("MI_LLM_BASE_URL and MI_LLM_MODEL must be configured together")
        if not api_key:
            return None
        return cls(validate_llm_base_url(base_url), model[:200], api_key, timeout=15.0)

    @property
    def endpoint(self):
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        path = urlsplit(self.base_url).path.rstrip("/")
        if path.endswith("/v1") or "/v1/" in path:
            return self.base_url + "/chat/completions"
        return self.base_url + "/v1/chat/completions"


def configured():
    try:
        return LLMConfig.from_env() is not None
    except ValueError:
        return False


def endpoint(base_url):
    base = validate_llm_base_url(base_url)
    return LLMConfig(base, "unused").endpoint


def _read_limited(response):
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("LLM response too large")
    return body


def request_json(config, system_prompt, user_payload):
    if not isinstance(config, LLMConfig):
        raise ValueError("invalid LLM configuration")
    body = json.dumps({
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if config.api_key:
        headers["Authorization"] = "Bearer " + config.api_key
    request = Request(config.endpoint, data=body, headers=headers, method="POST")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=config.timeout) as response:
        raw = _read_limited(response)
    parsed = strict_json_loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be an object")
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("LLM response has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("LLM response has no string content")
    content = strict_json_loads(message["content"])
    if not isinstance(content, dict):
        raise ValueError("LLM content must be a JSON object")
    return content


SYSTEM_PROMPT = """You are an optional bilingual writing assistant for a deterministic Meaning Intelligence tool.
Return only one strict JSON object, with no markdown, using exactly these optional keys:
summary_zh (string <=400 chars), summary_en (string <=400 chars),
questions_zh (array <=5 of strings <=300 chars), questions_en (array <=5 of strings <=300 chars),
safety_notes_zh (string <=400 chars), safety_notes_en (string <=400 chars).
Never invent empirical evidence, evidence levels, measurements, approvals, or execution. Preserve uncertainty.
Never request or reveal credentials. Do not include keys outside this list."""

LEGACY_SYSTEM_PROMPT = """Return only a strict JSON object. Allowed keys: summary, clarification_questions,
revision_suggestions, boundary_reminders. Do not invent evidence, approve, sum scales, or execute actions."""


def validate_enhancement(value):
    if not isinstance(value, dict):
        raise ValueError("enhancement must be an object")
    allowed = {"summary_zh", "summary_en", "questions_zh", "questions_en", "safety_notes_zh", "safety_notes_en"}
    if set(value) - allowed:
        raise ValueError("unexpected enhancement keys")
    result = {}
    for key, item in value.items():
        if key.startswith("questions_"):
            if not isinstance(item, list) or len(item) > 5 or any(not isinstance(entry, str) for entry in item):
                raise ValueError("invalid question list")
            result[key] = [redact_text(entry)[:300] for entry in item]
        else:
            if not isinstance(item, str):
                raise ValueError("invalid enhancement string")
            result[key] = redact_text(item)[:400]
    return result


def validate_suggestions(value):
    if not isinstance(value, dict):
        raise ValueError("suggestions must be an object")
    result = {}
    for key in ALLOWED_FIELDS:
        if key not in value:
            continue
        item = value[key]
        if key == "summary":
            if not isinstance(item, str):
                raise ValueError("summary must be text")
            result[key] = redact_text(item[:800])
        else:
            if not isinstance(item, list) or any(not isinstance(entry, str) for entry in item):
                raise ValueError(f"{key} must be a text list")
            result[key] = [redact_text(entry[:500]) for entry in item[:8]]
    if not result:
        raise ValueError("no allowed suggestion fields")
    return result


def request_suggestions(text, context):
    config = LLMConfig.from_env()
    if config is None:
        raise ValueError("LLM is not configured")
    raw = request_json(config, LEGACY_SYSTEM_PROMPT, {
        "text": redact_text(text)[:20000], "context": context,
        "task": "Suggest concise language only; deterministic results remain authoritative.",
    })
    return validate_suggestions(raw)


def assist(text, context, deterministic_summary):
    try:
        config = LLMConfig.from_env()
    except ValueError as exc:
        return {"status": "configuration_error", "error": safe_error(exc), "output": None}
    if config is None:
        return {"status": "disabled", "error": None, "output": None}
    try:
        raw = request_json(config, SYSTEM_PROMPT, {"text": text, "context": context, "deterministic_summary": deterministic_summary})
        return {"status": "ok", "error": None, "output": validate_enhancement(raw), "model": config.model, "unverified": True}
    except Exception as exc:  # Adapter failures must not break deterministic analysis.
        return {"status": "error", "error": safe_error(exc), "output": None}


def safe_failure(exc):
    error = safe_error(exc)
    return {"category": error["code"], "message": error["message"], "secret_details_exposed": False}
