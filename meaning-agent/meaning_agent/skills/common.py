"""Shared deterministic skill helpers."""

from ..i18n import bi, text_language
from ..safety import sanitize_context


def unique(items):
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def envelope(spec, data=None, questions=None, status=None):
    questions = unique(questions or [])
    return {
        "name": spec.name,
        "description": spec.description,
        "description_en": spec.description_en,
        "layer": spec.layer,
        "input": spec.input,
        "output": spec.output,
        "implementation": spec.implementation,
        "status": status or ("needs_clarification" if questions else "ok"),
        "needs_clarification": questions,
        "data": data or {},
    }


def inputs(payload):
    if not isinstance(payload, dict):
        payload = {}
    text = payload.get("text", "")
    if not isinstance(text, str):
        text = ""
    context = payload.get("context", {})
    if not isinstance(context, dict):
        context = {}
    return text.strip(), sanitize_context(context)


def missing_text(spec):
    return envelope(
        spec,
        status="needs_clarification",
        questions=[bi("请提供需要分析的非空文本。", "Provide non-empty text to analyze.")],
    )


def detect_language(text):
    return text_language(text)


def clarification(code, question):
    if isinstance(question, dict):
        text = question
    else:
        text = bi(str(question), str(question))
    return {"code": str(code), "question": text, "text": text}


def label(zh, en):
    return bi(zh, en)
