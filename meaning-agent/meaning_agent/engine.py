"""Deterministic six-layer pipeline plus optional, non-authoritative LLM writing."""

from copy import deepcopy

from .constants import PROVENANCE, SCALE_ALIASES, SCHEMA_VERSION
from .i18n import bi
from .llm import assist
from .rendering import to_markdown
from .safety import prepare_text, sanitize_context
from .skills.registry import SKILLS

APPROVAL_STATES = ("pending", "approved", "rejected")
DEMO_TEXT = (
    "研究显示新系统可以提高信任，但尚未提供数据来源。个人希望保留自主，组织担心成本，"
    "城市关注公平；当预算超过100万元时必须暂停。我们应如何在不加权求和的情况下校准五个尺度？"
    "如果方向漂移超过30%，应进行受控归零。"
)


def approval_record(status="pending"):
    if status not in APPROVAL_STATES:
        raise ValueError("approval must be pending, approved, or rejected")
    return {
        "status": status,
        "human_required": True,
        "recorded_from": "explicit_human_input" if status != "pending" else "default",
        "execution_authorized": False,
        "note": bi(
            "批准仅记录人工决定；本工具不执行决策、命令或文件操作。",
            "Approval records a human decision only; this tool executes no decisions, commands, or file operations.",
        ),
    }


def _summary(text, l1):
    separation = l1["data"]["fact_question_separation"]
    statements = separation["reported_statements"]
    questions = separation["open_questions"]
    count = len(statements)
    qcount = len(questions)
    excerpt = " / ".join(item["text"] for item in statements[:2])[:240]
    return {
        "zh": f"提取 {count} 条陈述、{qcount} 个开放问题和关键约束；经验断言仍未核实。摘录：{excerpt}",
        "en": f"Extracted {count} statements, {qcount} open questions, and key constraints; empirical claims remain unverified. Excerpt: {excerpt}",
        "source": "deterministic_pipeline",
    }


def _assistance(text, context, summary, use_llm):
    if use_llm is False:
        return {"status": "disabled_by_request", "error": None, "output": None}
    return assist(text, context, summary)


def analyze(text, context=None, scales=None, *, use_llm=None):
    if not isinstance(context, (dict, type(None))):
        raise ValueError("context must be an object")
    clean_text, text_metadata = prepare_text(text)
    if not clean_text:
        raise ValueError("text must be non-empty")
    clean_context = sanitize_context(context or {})
    if scales is not None:
        if not isinstance(scales, (list, tuple)):
            raise ValueError("scales must be a list")
        normalized_scales = []
        for item in scales:
            scale = SCALE_ALIASES.get(str(item).strip().lower()) if isinstance(item, str) else None
            if scale and scale not in normalized_scales:
                normalized_scales.append(scale)
        clean_context["selected_scales"] = normalized_scales
    payload = {"text": clean_text, "context": clean_context, "scales": clean_context.get("selected_scales")}
    upstream = {}
    results = []
    runners = tuple(runner for _, runner in SKILLS[:5])
    for runner in runners:
        layer_payload = dict(payload)
        layer_payload["upstream"] = upstream
        result = runner(layer_payload)
        results.append(result)
        upstream[result["layer"]] = result
    l6 = SKILLS[5][1]({"text": clean_text, "context": clean_context, "analysis": {"skills": {item["layer"]: item for item in results}}})
    results.append(l6)
    summary = _summary(clean_text, results[0])
    assistance = _assistance(clean_text, clean_context, summary, use_llm)
    if assistance.get("status") == "ok" and assistance.get("output"):
        llm_summary = assistance["output"]
        summary = {
            "zh": llm_summary.get("summary_zh", summary["zh"]),
            "en": llm_summary.get("summary_en", summary["en"]),
            "source": "configured_llm_unverified",
        }
    open_questions = [item["text"] for item in results[0]["data"]["fact_question_separation"]["open_questions"]]
    if assistance.get("status") == "ok" and assistance.get("output"):
        open_questions.extend(assistance["output"].get("questions_zh", []))
        open_questions.extend(assistance["output"].get("questions_en", []))
    if assistance.get("status") == "ok":
        mode = "llm"
    elif assistance.get("status") in ("error", "configuration_error"):
        mode = "offline_fallback"
    else:
        mode = "offline"
    skill_map = {item["layer"]: item for item in results}
    clarifications = []
    for item in results:
        clarifications.extend(item.get("needs_clarification", []))
    approval = approval_record()
    result = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": "1.0.0",
        "kind": "meaning_analysis",
        "language": "zh+en",
        "mode": mode,
        "status": "pending_human_approval",
        "input": {"text": clean_text, "context": clean_context, "text_metadata": text_metadata, "scales": clean_context.get("selected_scales")},
        "summary": summary,
        "clarifying_questions": open_questions,
        "needs_clarification": clarifications,
        "skills": skill_map,
        "skill_list": results,
        "approval": approval,
        "approval_gate": approval,
        "llm_assistance": assistance,
        "llm_suggestions": assistance.get("output"),
        "safety": {
            "offline_deterministic_core": True,
            "human_final_approval": True,
            "professional_judgment_not_replaced": True,
            "arbitrary_file_or_command_execution": False,
            "weighted_scale_summation": False,
        },
        "review_history": [],
        "provenance": {
            **PROVENANCE,
            "method": "standard_library_deterministic_heuristics",
            "external_fact_checking": False,
        },
        "limits": bi(
            "词法与规则启发式不是心理测量、实证验证、法律意见或安全认证；不执行任何操作。",
            "Lexical and rule heuristics are not psychometrics, empirical validation, legal advice, or safety certification; no actions are executed.",
        ),
    }
    result["markdown"] = to_markdown(result)
    return result


def _review_analysis(analysis, approval="pending", feedback=None):
    record = approval_record(approval)
    reviewed = SKILLS[5][1]({
        "text": analysis.get("input", {}).get("text", ""),
        "context": analysis.get("input", {}).get("context", {}),
        "analysis": analysis,
        "feedback": feedback or {},
    })
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "meaning_review",
        "language": "zh+en",
        "mode": analysis.get("mode", "offline"),
        "status": "review_complete_pending_human" if approval == "pending" else "human_decision_recorded",
        "analysis": analysis,
        "review": reviewed,
        "approval": record,
        "approval_gate": record,
        "execution": {"performed": False, "reason": "read_only_review_only"},
    }
    result["markdown"] = to_markdown(result)
    return result


def review(text, context=None, approval="pending", use_llm=None):
    if isinstance(text, dict):
        previous = text
        if not isinstance(previous.get("skills"), dict):
            raise ValueError("previous must be a meaning analysis object")
        raw_feedback = context if context is not None else {}
        clean_feedback = sanitize_context(raw_feedback if isinstance(raw_feedback, dict) else {"text": str(raw_feedback)})
        corrected = clean_feedback.get("corrected_text")
        if clean_feedback.get("action") == "replace_text":
            corrected = clean_feedback.get("text")
        reanalyzed = isinstance(corrected, str) and bool(corrected.strip())
        if reanalyzed:
            old_context = previous.get("input", {}).get("context", {})
            feedback_context = clean_feedback.get("context", {})
            if not isinstance(feedback_context, dict):
                feedback_context = {}
            analysis = analyze(corrected, context={**old_context, **feedback_context}, use_llm=False)
        else:
            analysis = previous
        result = _review_analysis(analysis, approval="pending", feedback=clean_feedback)
        review_data = result["review"]["data"]
        revision_required = bool(review_data.get("revision_required")) or reanalyzed
        revised_analysis = deepcopy(analysis)
        revised_analysis["skills"]["L6"] = result["review"]
        if revision_required:
            pending = approval_record()
            revised_analysis["approval"] = pending
            revised_analysis["approval_gate"] = pending
            revised_analysis["status"] = "pending_human_approval"
        history = list(revised_analysis.get("review_history", []))
        history.append({"feedback": clean_feedback, "revision_required": revision_required, "human_approval": "pending"})
        revised_analysis["review_history"] = history[-20:]
        revised_analysis["markdown"] = to_markdown(revised_analysis)
        result.update({
            "mode": "offline",
            "revision_required": revision_required,
            "review_triggers": review_data.get("review_triggers", []),
            "affected_skills": review_data.get("affected_skills", []),
            "revision_suggestions": review_data.get("revision_suggestions", []),
            "feedback": clean_feedback,
            "revised_analysis": revised_analysis,
        })
        result["markdown"] = to_markdown(result)
        return result
    analysis = analyze(text, context=context, use_llm=use_llm)
    return _review_analysis(analysis, approval=approval)


def demo(use_llm=None, as_json=False):
    analysis = analyze(DEMO_TEXT, use_llm=use_llm)
    result = {**_review_analysis(analysis), "schema_version": SCHEMA_VERSION, "kind": "meaning_demo", "language": "zh+en", "demo_text": DEMO_TEXT}
    result["markdown"] = to_markdown(result)
    return result if as_json else result["markdown"]
