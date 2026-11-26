"""L2: suggest safe experiential HTML and adjustable interaction parameters."""

import html
import re

from ..constants import SCALES
from ..i18n import bi
from ..models import SkillSpec
from .common import envelope, inputs, missing_text

SPEC = SkillSpec(
    name="model-experiential-interface",
    description="把意义体验表达为可调节的交互参数，并给出离线、无网络请求的 HTML 原型。",
    description_en="Express meaning experience as adjustable interaction parameters and provide an offline HTML prototype with no network requests.",
    layer="L2",
    input="text: str; context: dict; upstream.L1: dict",
    output="parameters, safe_html_suggestion, experiential_principles",
    implementation="meaning_agent.skills.l2_experiential.run",
)

INTERACTION_SCRIPT = """<script>
(function () {
  document.querySelectorAll('[data-mi-layer="L2"]').forEach(function (root) {
    var range = root.querySelector('[data-mi-detail]');
    var nodes = Array.prototype.slice.call(root.querySelectorAll('[data-mi-node]'));
    if (!range || !nodes.length) return;
    range.disabled = false;
    function update() {
      var count = Number(range.value);
      nodes.forEach(function (node, index) { node.hidden = index >= count; });
    }
    range.addEventListener('input', update);
    update();
  });
}());
</script>"""


def run(payload):
    text, context = inputs(payload)
    if not text:
        return missing_text(SPEC)
    lowered = text.lower()
    load = "high" if len(text) > 1200 or re.search(r"复杂|超载|overwhelm", lowered) else "medium"
    agency = "human" if re.search(r"人类|人工|批准|human|approval", lowered) else "shared"
    pace = "user_controlled" if re.search(r"自己|自主|user|autonomy", lowered) else "adjustable"
    reversible = not bool(re.search(r"不可逆|永久|irreversible|permanent", lowered))
    feedback = "immediate" if re.search(r"即时|反馈|immediate|feedback", lowered) else "on_request"
    upstream = payload.get("upstream", {})
    l1 = upstream.get("L1", {}) if isinstance(upstream, dict) else {}
    structure = l1.get("data", {}).get("key_structure", {}) if isinstance(l1, dict) else {}
    nodes = structure.get("nodes", []) if isinstance(structure, dict) else []
    questions = l1.get("data", {}).get("fact_question_separation", {}).get("open_questions", []) if isinstance(l1, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(questions, list):
        questions = []
    node_items = "".join(
        f'<li data-mi-node><strong>{html.escape(str(node.get("label", ""))[:80])}</strong> '
        f"<span>{html.escape(str(node.get('mentions', '')))} mentions</span></li>"
        for node in nodes[:10] if isinstance(node, dict)
    ) or '<li data-mi-node>暂无可展示结构 / No structure available</li>'
    question_items = "".join(
        f"<li>{html.escape(str(question.get('text', ''))[:300])}</li>"
        for question in questions[:8] if isinstance(question, dict)
    ) or "<li>尚未识别出待决问题 / No open question detected</li>"
    maximum = max(1, min(10, len(nodes)))
    title = html.escape(str(context.get("title", "Meaning Intelligence / 意义智能"))[:120])
    safe_html = (
        '<section class="mi-experience" data-mi-layer="L2">'
        f"<h2>{title}</h2>"
        "<p>体验是可检验的参数，不是装饰。 / Experience is a testable parameter, not decoration.</p>"
        f'<label>建议细节层级 / Suggested detail level <input data-mi-detail type="range" min="1" max="{maximum}" value="{min(3, maximum)}"></label>'
        f"<ul>{node_items}</ul><details><summary>待决问题 / Open questions</summary><ul>{question_items}</ul></details>"
        '<label>你的批准 / Your approval <input type="checkbox" disabled></label>'
        "<p>安全建议片段无脚本、无网络请求；可选的固定本地交互脚本单独提供，且不代表批准。</p>"
        "</section>"
    )
    parameters = [
        {"id": "cognitive_load", "label": bi("认知负荷", "Cognitive load"), "suggested_value": load,
         "options": ["low", "medium", "high"], "rationale": bi("由文本长度与负荷词启发；不是测量。", "Heuristic from length and load terms; not a measurement.")},
        {"id": "agency", "label": bi("行动主体", "Agency"), "suggested_value": agency,
         "options": ["human", "shared", "assistant"], "rationale": bi("最终批准保留给人类。", "Final approval remains with a human.")},
        {"id": "feedback_timing", "label": bi("反馈时机", "Feedback timing"), "suggested_value": feedback,
         "options": ["immediate", "on_request", "delayed"], "rationale": bi("反馈应可被用户控制或请求。", "Feedback should be user-controlled or requested.")},
        {"id": "pace", "label": bi("节奏", "Pace"), "suggested_value": pace,
         "options": ["adjustable", "user_controlled", "fixed"], "rationale": bi("建议允许暂停和回看。", "Allow pauses and review.")},
        {"id": "reversibility", "label": bi("可逆性", "Reversibility"), "suggested_value": reversible,
         "rationale": bi("不可逆表述会提高复核要求。", "Irreversibility language raises review requirements.")},
    ]
    parameter_suggestions = [
        {"name": "detail_level", "type": "range", "min": 1, "max": maximum, "default": min(3, maximum), "implemented": True,
         "effect": bi("在离线 HTML 中调节可见节点数量；只改变呈现，不增加证据。", "Adjust visible node count in the offline HTML; presentation only, not evidence.")},
        {"name": "scale_focus", "type": "select", "options": [item[0] for item in SCALES], "implemented": False,
         "effect": bi("仅显示该尺度的显式材料；不得推测未提供的立场。", "Show only explicit material at that scale; do not infer unsupplied positions.")},
        {"name": "time_horizon", "type": "select", "options": ["immediate", "short", "long"], "implemented": False,
         "effect": bi("仅按用户提供的时距重排，不自动设定。", "Reorder only with a user-supplied horizon; never set it automatically.")},
    ]
    data = {
        "title": bi("体验界面参数", "Experiential interface parameters"),
        "format": "standalone_html_fragment",
        "parameters": parameters,
        "parameter_suggestions": parameter_suggestions,
        "safe_html_suggestion": safe_html,
        "interactive_html": safe_html + INTERACTION_SCRIPT,
        "html_safety": {"scripts": False, "network": False, "execution": "local_display_only", "purpose": "script_free_safe_suggestion", "user_content_escaped": True, "interactive_html_scripts": True, "interactive_html_execution": "opt_in_fixed_local_script_only"},
        "experiential_principles": [
            bi("让用户感知方向、价值和边界，而非只展示结论。", "Let users perceive direction, value, and boundaries rather than only conclusions."),
            bi("所有参数都是可讨论的建议，必须经人类批准。", "Treat every parameter as a discussable suggestion requiring human approval."),
            bi("不把主观体验伪装为经验证事实。", "Do not present subjective experience as empirically verified fact."),
        ],
        "replay_steps": [
            bi("调节细节层级", "Adjust detail level"),
            bi("核对节点是否来自原文", "Check nodes against the source"),
            bi("展开待决问题", "Expand open questions"),
        ],
        "experience_is_not_validation": True,
        "requested_context": context.get("requested_context", []),
    }
    return envelope(SPEC, data)
