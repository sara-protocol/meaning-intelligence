import re
from datetime import date

from ..constants import CORRECTION_LEVELS
from ..i18n import bi
from ..models import SkillSpec
from .common import clarification, envelope, inputs, missing_text, unique

SPEC = SkillSpec(
    name="recursive-review-zeroing",
    description="生成元认知问题、复核触发与受控归零建议，审查反馈并重置已失效的人工批准。",
    description_en="Generate metacognition questions, review triggers, and controlled-zeroing suggestions; inspect feedback and reset invalidated human approval.",
    layer="L6",
    input="text: str; context: dict; analysis/previous: dict; feedback: str|dict",
    output="metacognition_questions, review_triggers, zeroing_plan, revision_suggestions, approval_gate",
    implementation="meaning_agent.skills.l6_recursive.run",
)

HIGH_STAKES = (
    ("medical", r"医疗|诊断|用药|疾病|症状|\b(?:medical|diagnosis|medication|disease)\b"),
    ("legal", r"法律|诉讼|合同|合规|\b(?:legal|lawsuit|contract|compliance)\b"),
    ("financial", r"投资|理财|证券|财务|\b(?:investment|securities|financial)\b"),
    ("safety", r"安全|事故|逃生|工程|\b(?:safety|accident|emergency)\b"),
    ("employment", r"招聘|解雇|晋升|绩效|\b(?:hiring|firing|promotion)\b"),
)


def feedback_actions(feedback):
    if isinstance(feedback, dict):
        action = str(feedback.get("action", "")).lower()
        if action == "replace_text":
            action = "correction"
        text = " ".join(str(feedback.get(key, "")) for key in ("correction", "reason", "note", "feedback", "text"))
    else:
        action = ""
        text = str(feedback or "")
    lowered = text.lower()
    result = []
    patterns = (
        ("zero", r"归零|重置|重新开始|推倒|\b(?:zero|reset|start over)\b"),
        ("evidence", r"证据|来源|数据|复核|证伪|\b(?:evidence|source|data|falsif)\b"),
        ("scale", r"尺度|冲突|个人|组织|城市|国家|人类|\b(?:scale|conflict)\b"),
        ("boundary", r"边界|期限|范围|成本|代价|\b(?:boundary|deadline|cost)\b"),
        ("correction", r"错误|不准确|遗漏|更正|纠正|不对|\b(?:wrong|incorrect|missing|correct)\b"),
        ("clarify", r"澄清|补充|说明|问题|\b(?:clarify|explain|question)\b"),
        ("approval", r"批准|认可|通过|\b(?:approve|approval)\b"),
    )
    for name, pattern in patterns:
        if re.search(pattern, lowered, re.I) or name in action:
            result.append(name)
    return unique(result)


def run(payload):
    text, context = inputs(payload)
    if not text and not isinstance(payload.get("analysis"), dict) and not isinstance(payload.get("previous"), dict):
        return missing_text(SPEC)
    analysis = payload.get("analysis", payload.get("previous", {}))
    if not isinstance(analysis, dict):
        analysis = {}
    feedback = payload.get("feedback", "")
    actions = feedback_actions(feedback)
    triggers = []
    affected = []
    if actions:
        mapping = {"zero": ["L1", "L3", "L5", "L6"], "evidence": ["L4"], "scale": ["L5"], "boundary": ["L3", "L5"], "correction": ["L1", "L3", "L4"], "clarify": ["L1", "L3"], "approval": ["L6"]}
        for action in actions:
            layers = mapping[action]
            affected.extend(layers)
            triggers.append({"code": f"feedback_{action}", "severity": "high" if action in ("zero", "correction") else "medium", "affected_skills": layers, "reason": f"用户反馈触发{action}复核。"})
    skills = analysis.get("skills", {})
    if isinstance(skills, dict):
        for layer, result in skills.items():
            if isinstance(result, dict) and (result.get("status") == "needs_clarification" or result.get("needs_clarification")):
                triggers.append({"code": f"{layer}_clarification", "severity": "medium", "affected_skills": [layer], "reason": "上游技能仍有未满足的信息条件。"})
                affected.append(layer)
    l5 = skills.get("L5", {}) if isinstance(skills, dict) else {}
    l5_data = l5.get("data", {}) if isinstance(l5, dict) else {}
    if l5_data.get("conflicts"):
        triggers.append({"code": "unresolved_scale_conflict", "severity": "high", "affected_skills": ["L5", "L6"], "reason": "尺度冲突尚未完成递归校准。"})
        affected.extend(["L5", "L6"])
    expires_on = l5_data.get("expires_on")
    if isinstance(expires_on, str):
        try:
            if date.fromisoformat(expires_on) <= date.today():
                triggers.append({"code": "direction_expired", "severity": "high", "affected_skills": ["L5", "L6"], "reason": "方向已到达失效日期。"})
        except ValueError:
            triggers.append({"code": "expiry_invalid", "severity": "medium", "affected_skills": ["L5"], "reason": "失效日期不是有效 ISO 日期。"})
    professional_domains = [domain for domain, pattern in HIGH_STAKES if re.search(pattern, text, re.I)]
    if professional_domains:
        triggers.append({"code": "professional_review_required", "severity": "high", "affected_skills": ["L6"], "reason": "输入涉及需要专业判断的领域。"})
    zero_requested = "zero" in actions or context.get("zeroing_requested") is True
    previous_gate = analysis.get("approval_gate", {})
    if not isinstance(previous_gate, dict):
        previous_gate = {}
    revision_required = any(item["severity"] == "high" for item in triggers) or any(action != "approval" for action in actions)
    approval_status = "pending" if revision_required else previous_gate.get("status", "pending")
    if approval_status != "pending" and revision_required:
        approval_status = "pending"
    suggestions = []
    if any(item["code"].endswith("clarification") for item in triggers):
        suggestions.append("先补齐上游 needs_clarification，再重跑六技能；不得用默认值填空。")
    if "evidence" in actions or any(item["code"] == "L4_clarification" for item in triggers):
        suggestions.append("为每个关键判断补来源、预注册方案与独立核验记录；保持实证等级未授予。")
    if "scale" in actions or l5_data.get("conflicts"):
        suggestions.append("逐对回到元意义层校准冲突，写明优先级、代价与暂停条件；不做加权求和。")
    if "correction" in actions:
        suggestions.append("把更正内容作为新证据重新进入 L1，并保留旧版本以便复核。")
    if zero_requested:
        suggestions.append("执行受控归零：先保存原文与证据，再重问目的、价值和边界；不自动推倒重来。")
    if professional_domains:
        suggestions.append("暂停自动化建议，交由相应领域专业人员审查。")
    if not suggestions:
        suggestions.append("保留当前候选，按用户定义的日期或新证据触发下一轮复核。")
    data = {
        "metacognition_questions": [
            "我为何这样判断？哪些是原文，哪些是启发式候选？",
            "哪个前提若被推翻，会改变整个方向？",
            "谁受益、谁承担代价、谁没有发言？",
            "什么证据会证明这个判断错误？",
            "是否把个人尺度误当成组织、国家或人类尺度？",
            "是否存在更简洁且解释力更强的结构？",
            "继续审视是否会造成决策瘫痪？",
        ],
        "review_triggers": triggers,
        "revision_required": revision_required,
        "affected_skills": unique(affected),
        "zeroing_plan": {
            "recommended": zero_requested,
            "mode": "controlled_reset" if zero_requested else "not_requested",
            "requires_human_approval": True,
            "safety_check": ["保存原文和证据", "明确重置范围", "确认关键服务与责任不中断", "记录保留项与重构项", "设置重新进入 L1 的标准"],
            "preserve": ["原始文本", "来源记录", "已承担的责任", "可复核反馈"],
            "reset": ["目的假设", "方向候选", "价值排序", "边界条件"],
            "reentry": "L1_prime_with_updated_input_criteria",
        },
        "revision_suggestions": suggestions,
        "review_passes": [
            {"pass": 1, "focus": bi("检查来源、事实与候选解释的边界。", "Check sources, facts, and the boundaries of candidate interpretations."), "new_issue_count": len(triggers), "stop_reason": "max_three_passes"},
            {"pass": 2, "focus": bi("检查尺度冲突、优先级、代价与沉默者。", "Check scale conflicts, priorities, costs, and missing voices."), "new_issue_count": 0, "stop_reason": "max_three_passes"},
            {"pass": 3, "focus": bi("检查归零是否可逆、批准是否仍有效。", "Check whether zeroing is reversible and approval remains valid."), "new_issue_count": 0, "stop_reason": "max_three_passes"},
        ],
        "zeroing_protocol": {
            "reversible": True,
            "data_deleted": False,
            "execution_allowed": False,
            "requires_human_approval": True,
            "steps": [
                bi("保存原始文本、来源、反馈与责任记录。", "Preserve original text, sources, feedback, and responsibility records."),
                bi("明确要重置的假设以及必须保留的边界。", "Specify assumptions to reset and boundaries that must be preserved."),
                bi("由人类确认服务与责任不会中断。", "Have a human confirm that services and responsibilities will not be interrupted."),
                bi("记录保留项和重构项，以新输入条件重新进入 L1。", "Record preserved and reconstructed items; re-enter L1 with updated input criteria."),
            ],
            "preserve": ["原始文本", "来源记录", "已承担的责任", "可复核反馈"],
            "reset": ["目的假设", "方向候选", "价值排序", "边界条件"],
        },
        "correction_levels": [dict(item) for item in CORRECTION_LEVELS],
        "limitations": bi(
            "三轮审视是有界启发式，不能证明无偏、真实或安全，也不替代专业判断。",
            "Three review passes are bounded heuristics; they do not prove impartiality, truth, or safety and do not replace professional judgment.",
        ),
        "approval_status": "pending_human" if approval_status == "pending" else "human_recorded_not_execution",
        "approval_gate": {
            "status": approval_status,
            "authority": "human",
            "automated_approval": False,
            "approval_request_is_not_approval": "approval" in actions,
            "professional_judgment_not_replaced": True,
            "required_professional_domains": professional_domains,
        },
        "next_review_triggers": ["新证据到达", "尺度冲突出现", "边界或代价改变", "方向到达失效日期", "用户要求归零"],
        "automatic_execution": False,
    }
    questions = []
    if revision_required:
        questions.append(clarification("revision_unresolved", bi("请补充触发复核的信息，并由人类决定是否采纳修订建议。", "Supply the information that triggered review; a human must decide whether to adopt the revision suggestions.")))
    return envelope(SPEC, data, questions, status="needs_clarification" if revision_required else None)
