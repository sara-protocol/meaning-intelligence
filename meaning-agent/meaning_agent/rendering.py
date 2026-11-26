"""Deterministic bilingual Markdown rendering for CLI output."""

import json

from .i18n import pick


def md(value):
    if value is None or value == "":
        return "未提供 / Not provided"
    if isinstance(value, (dict, list, tuple)):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return rendered.replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ")
    return str(value).replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ")


def localized(value, language="zh"):
    if isinstance(value, dict):
        return md(pick(value, language))
    if isinstance(value, list):
        return "；".join(localized(item, language) for item in value)
    return md(value)


def _skills(result):
    skills = result.get("skills", {})
    if isinstance(skills, dict):
        return [skills[key] for key in ("L1", "L2", "L3", "L4", "L5", "L6") if key in skills]
    return skills if isinstance(skills, list) else []


def _clarification_lines(items):
    lines = []
    for item in items or []:
        if not isinstance(item, dict):
            lines.append("- " + md(item))
            continue
        code = item.get("code", "clarification")
        question = item.get("question", item.get("text", item))
        lines.append(f"- `{md(code)}` {localized(question, 'zh')} / {localized(question, 'en')}")
    return lines or ["- 无 / None"]


def to_markdown(result):
    if not isinstance(result, dict):
        return ""
    analysis = result.get("revised_analysis", result.get("analysis", result))
    if not isinstance(analysis, dict):
        analysis = result
    lines = ["# Meaning Intelligence / 意义智能", ""]
    lines.extend([f"- Kind / 类型: `{md(result.get('kind', 'meaning_analysis'))}`", f"- Mode / 模式: `{md(result.get('mode', 'offline'))}`", ""])

    summary = analysis.get("summary")
    lines.extend(["## Summary / 摘要", ""])
    if isinstance(summary, dict):
        lines.extend([f"- 中文: {localized(summary, 'zh')}", f"- English: {localized(summary, 'en')}", ""])
    else:
        lines.extend([md(summary), ""])

    approval = result.get("approval_gate", analysis.get("approval_gate", analysis.get("approval", {})))
    if not isinstance(approval, dict):
        approval = {}
    lines.extend([
        "## Approval / 人工批准", "",
        f"- Status / 状态: `{md(approval.get('status', 'pending'))}`",
        "- Human required / 需要人类: yes / 是",
        "- Execution authorized / 授权执行: no / 否",
        "- Professional judgment replaced / 替代专业判断: no / 否",
        "",
    ])

    lines.extend(["## Clarification / 待澄清", ""])
    lines.extend(_clarification_lines(analysis.get("needs_clarification", [])))
    lines.append("")

    for skill in _skills(analysis):
        if not isinstance(skill, dict):
            continue
        layer = skill.get("layer", "")
        data = skill.get("data", {})
        if not isinstance(data, dict):
            continue
        lines.extend([f"## {layer} · {skill.get('name', '')}", "", localized(skill.get("description", ""), "zh"), localized(skill.get("description_en", ""), "en"), ""])

        if layer == "L1":
            separation = data.get("fact_question_separation", {})
            lines.append("**陈述 / Statements（均未核实 / all unverified）**")
            statements = separation.get("reported_statements", []) if isinstance(separation, dict) else []
            lines.extend([f"- {md(item.get('text'))} [{md(item.get('kind'))}]" for item in statements if isinstance(item, dict)] or ["- 无 / None"])
            lines.extend(["", "**开放问题 / Open questions**"])
            questions = separation.get("open_questions", []) if isinstance(separation, dict) else []
            lines.extend([f"- {md(item.get('text'))}" for item in questions if isinstance(item, dict)] or ["- 无 / None"])
            lines.extend(["", f"- Key structure / 关键结构: {md(data.get('key_structure'))}", f"- Constraints / 约束: {md(data.get('critical_constraints'))}", ""])

        elif layer == "L2":
            lines.extend([
                f"- Parameters / 参数: {md(data.get('parameters'))}",
                f"- Parameter suggestions / 参数建议: {md(data.get('parameter_suggestions'))}",
                f"- HTML safety / HTML 安全: {md(data.get('html_safety'))}",
                "- `safe_html_suggestion` is script-free; separate `interactive_html` uses a fixed local-display-only script and is not executed here. / `safe_html_suggestion` 无脚本；单独的 `interactive_html` 仅使用固定本地显示脚本，此处不执行。",
                "",
            ])

        elif layer == "L3":
            dimensions = data.get("dimensions", {})
            lines.extend([f"- Direction / 方向: {md(dimensions.get('direction'))}", f"- Value / 价值: {md(dimensions.get('value'))}", f"- Boundary / 边界: {md(dimensions.get('boundary'))}", f"- Continuous spectrum / 连续光谱: {md(data.get('spectrum'))}", ""])

        elif layer == "L4":
            lines.extend([f"- Automatic empirical level / 自动实证等级: `{md(data.get('automatic_empirical_level'))}`", "- Automatic empirical-level claim / 自动声称实证等级: no / 否", "", "**E0–E6 reference / 证据参考**"])
            lines.extend([f"- {item.get('id')} {item.get('name')} / {item.get('name_en')}: {item.get('definition')} / {item.get('definition_en')}" for item in data.get("reference_scale", [])])
            lines.extend(["", "**User evidence / 用户证据（未独立核验）**"])
            lines.extend([f"- {md(item.get('source'))}: {md(item.get('description'))}; claimed / 声明={md(item.get('claimed_level'))}; accepted / 接受={md(item.get('accepted_level'))}" for item in data.get("evidence_items", [])] or ["- 无 / None"])
            lines.extend(["", "**Claim assessments / 主张评估（未独立核验）**"])
            lines.extend([f"- {md(item.get('claim_id'))}: level / 等级={md(item.get('level'))}; status / 状态={md(item.get('current_empirical_status'))}; {md(item.get('claim'))}" for item in data.get("claim_assessments", [])] or ["- 无 / None"])
            lines.extend(["", "**Falsification plans / 证伪计划（未检验）**"])
            lines.extend([f"- {md(item.get('claim_id'))}: {localized(item.get('falsifier'), 'zh')} / {localized(item.get('falsifier'), 'en')} [not_tested / 未检验]" for item in data.get("falsification_plans", [])] or ["- 无 / None"])
            lines.extend(["", "**Canon hypotheses / 正典假设（记录等级，不是新认定）**"])
            lines.extend([f"- {item.get('id')} {item.get('name')} [{md(item.get('recorded_level'))}]: {md(item.get('falsifier'))}" for item in data.get("linked_hypotheses", [])])
            lines.extend(["", "**Appendix D.7 / 附录 D.7**"])
            lines.extend([f"- {item.get('id')} {item.get('name')}: {md(item.get('failure_threshold'))} → {md(item.get('action'))}" for item in data.get("appendix_d7", [])])
            lines.extend(["", "**Engineering drafts / 工程草案（未预注册，不可正式处置）**"])
            drafts = data.get("falsification_conditions", {}).get("engineering_drafts", [])
            lines.extend([f"- {item.get('layer')} [{md(item.get('scope'))}]: {md(item.get('condition'))} → {md(item.get('action'))}" for item in drafts])
            lines.append("")

        elif layer == "L5":
            lines.extend(["**Scale positions / 尺度立场**", "", "| Scale / 尺度 | Direction / 方向 | Alignment / 对齐 | Costs / 代价 |", "|---|---|---|---|"])
            for item in data.get("scale_positions", []):
                lines.append(f"| {md(item.get('scale'))} | {md(item.get('direction'))} | {md(item.get('alignment'))} | {md(item.get('costs'))} |")
            lines.extend(["", f"- Conflicts / 冲突: {md(data.get('conflicts'))}", f"- Priority order / 优先级: {md(data.get('priority_order'))}", f"- Costs / 代价: {md(data.get('costs'))}", f"- Triggers / 触发条件: {md(data.get('trigger_conditions'))}", f"- Expiry / 失效日期: {md(data.get('expires_on'))}", f"- Provisional direction / 暂定方向: {md(data.get('provisional_direction'))}", f"- Aggregation / 聚合: {md(data.get('aggregation'))}", "- Weighted summation / 加权求和: forbidden / 禁止", ""])

        elif layer == "L6":
            lines.extend(["**Metacognition / 元认知**"])
            lines.extend([f"- {md(item)}" for item in data.get("metacognition_questions", [])] or ["- 无 / None"])
            lines.extend(["", f"- Review triggers / 复核触发: {md(data.get('review_triggers'))}", f"- Affected skills / 受影响技能: {md(data.get('affected_skills'))}", f"- Revision required / 需要修订: {md(data.get('revision_required'))}", f"- Revision suggestions / 修订建议: {md(data.get('revision_suggestions'))}", f"- Controlled zeroing / 受控归零: {md(data.get('zeroing_plan'))}", ""])
            lines.extend(["**Bounded review passes / 有界递归审视**"])
            lines.extend([f"- Pass {item.get('pass')}: {localized(item.get('focus'), 'zh')} / {localized(item.get('focus'), 'en')}; stop={md(item.get('stop_reason'))}" for item in data.get("review_passes", [])] or ["- 无 / None"])
            lines.extend(["", f"- Zeroing protocol / 归零协议: {md(data.get('zeroing_protocol'))}", ""])

    if result.get("kind") == "meaning_review":
        review_data = result.get("review", {}).get("data", {})
        lines.extend(["## Feedback Review / 反馈修订", "", f"- Feedback / 反馈: {md(result.get('feedback'))}", f"- Revision required / 需要修订: {md(result.get('revision_required'))}", f"- Affected skills / 受影响技能: {md(result.get('affected_skills'))}", f"- Review triggers / 复核触发: {md(result.get('review_triggers', review_data.get('review_triggers')))}", f"- Revision suggestions / 修订建议: {md(result.get('revision_suggestions', review_data.get('revision_suggestions')))}", ""])

    provenance = analysis.get("provenance", {})
    if provenance:
        lines.extend(["## Provenance / 来源边界", "", md(provenance), ""])
    limits = analysis.get("limits")
    if limits:
        lines.extend(["## Limits / 局限", "", localized(limits, "zh"), "", localized(limits, "en"), ""])
    return "\n".join(lines).strip() + "\n"
