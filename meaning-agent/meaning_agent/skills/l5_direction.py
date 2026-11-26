from ..constants import CORRECTION_LEVELS, SCALES, SCALE_ALIASES
from ..i18n import bi
from ..models import SkillSpec
from .common import clarification, envelope, inputs, missing_text, unique

SPEC = SkillSpec(
    name="calibrate-five-scales",
    description="在个人、组织、城市、国家、人类五尺度上列方向、冲突、优先级、代价与触发条件，禁止加权求和。",
    description_en="List directions, conflicts, priorities, costs, and triggers across five incommensurable scales; weighted summation is forbidden.",
    layer="L5",
    input="text: str; context: dict; scales: list; upstream.L3/L4: dict",
    output="scale_positions, conflicts, priority_order, costs, correction_triggers, provisional_direction",
    implementation="meaning_agent.skills.l5_direction.run",
)


def canonical_scale(value):
    key = str(value).strip().lower()
    return SCALE_ALIASES.get(key)


def normalize_positions(raw):
    result = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        scale = canonical_scale(key)
        if not scale:
            continue
        if isinstance(value, str):
            result[scale] = {"direction": value}
        elif isinstance(value, dict):
            result[scale] = dict(value)
    return result


def selected_scales(payload, context):
    supplied = payload.get("scales")
    if supplied is None:
        supplied = context.get("scales")
    if supplied is None:
        return [item[0] for item in SCALES]
    if isinstance(supplied, str):
        supplied = [item.strip() for item in supplied.split(",") if item.strip()]
    if not isinstance(supplied, (list, tuple)):
        return []
    result = []
    for item in supplied:
        scale = canonical_scale(item)
        if scale and scale not in result:
            result.append(scale)
    return result


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def run(payload):
    text, context = inputs(payload)
    if not text:
        return missing_text(SPEC)
    scales = selected_scales(payload, context)
    if not scales:
        return envelope(SPEC, {}, [clarification("scales_missing", bi("请至少选择个人、组织、城市、国家、人类中的一个有效尺度。", "Select at least one valid scale: individual, organization, city, national, or humanity."))])
    upstream = payload.get("upstream", {})
    l3 = upstream.get("L3", {}) if isinstance(upstream, dict) else {}
    candidate = l3.get("data", {}).get("dimensions", {}).get("direction", {}).get("statement") if isinstance(l3, dict) else None
    explicit_direction = context.get("preferred_direction") or context.get("selected_direction") or context.get("direction")
    if isinstance(explicit_direction, str) and explicit_direction.strip():
        candidate = explicit_direction.strip()
        direction_basis = "explicit_user_preference"
    else:
        direction_basis = "candidate_from_text_not_a_commitment" if candidate else "not_provided"
    raw_positions = context.get("scale_positions", context.get("scales", {}))
    if not isinstance(raw_positions, dict):
        raw_positions = {}
    positions = normalize_positions(raw_positions)
    raw_costs = context.get("costs", {})
    if not isinstance(raw_costs, dict):
        raw_costs = {}
    scale_rows = []
    scale_labels = {key: bi(zh, en) for key, zh, en in SCALES}
    for scale in scales:
        row = positions.get(scale, {})
        direction = row.get("direction")
        alignment = row.get("alignment", "unknown")
        scale_costs = as_list(row.get("costs")) + as_list(raw_costs.get(scale))
        mentioned = bool(row) or any(cue in text.lower() for cue in (scale, scale_labels[scale]["zh"].lower(), scale_labels[scale]["en"].lower()))
        scale_row = {
            "scale": scale,
            "label": scale_labels[scale],
            "mentioned": mentioned,
            "score": None,
            "direction": direction,
            "alignment": alignment,
            "costs": scale_costs,
            "cost_status": "provided" if scale_costs else "not_provided",
            "basis": "explicit_context" if row else "text_signal_or_not_provided" if mentioned else "not_provided",
            "incommensurable_with_other_scales": True,
        }
        scale_rows.append(scale_row)
    conflicts = []
    explicit_conflicts = as_list(context.get("conflicts"))
    for index, conflict in enumerate(explicit_conflicts[:20]):
        if isinstance(conflict, dict):
            conflicts.append({**conflict, "id": f"c{index + 1}", "status": conflict.get("status", "unresolved")})
        else:
            conflicts.append({"id": f"c{index + 1}", "description": str(conflict), "status": "unresolved"})
    for left_index, left in enumerate(scale_rows):
        for right in scale_rows[left_index + 1:]:
            if left["alignment"] == "conflict" or right["alignment"] == "conflict":
                reason = "explicit_alignment_conflict"
            elif left["direction"] and right["direction"] and left["direction"].strip().lower() != right["direction"].strip().lower():
                reason = "explicit_directions_differ"
            else:
                continue
            conflicts.append({
                "id": f"c{len(conflicts) + 1}",
                "scales": [left["scale"], right["scale"]],
                "reason": reason,
                "status": "potential_conflict_requires_calibration" if reason == "explicit_directions_differ" else "unresolved",
                "priority": None,
                "cost": [item for item in left["costs"] + right["costs"]],
                "trigger_condition": "当尺度间代价或方向背离超过用户声明阈值时，回到元意义层校准。",
                "calibration_question": "哪一条边界或共同目的可以使这两个尺度重新对齐？不得用权重合并。",
            })
    raw_priorities = as_list(context.get("scale_priorities"))
    priorities = unique([canonical_scale(item) for item in raw_priorities if canonical_scale(item)])
    questions = []
    if not candidate:
        questions.append(clarification("direction_missing", bi("请给出候选方向；没有方向时本技能不作选择。", "Provide a candidate direction; without one, this skill makes no choice.")))
    missing_positions = [row["scale"] for row in scale_rows if not row["direction"]]
    if missing_positions:
        questions.append(clarification("scale_positions_missing", bi("请补充这些尺度的显式方向：" + "、".join(missing_positions), "Provide explicit directions for these scales: " + ", ".join(missing_positions))))
    if not priorities:
        questions.append(clarification("priority_missing", bi("请声明尺度优先级及其理由；优先级不是权重。", "State scale priorities and their rationale; priorities are not weights.")))
    if any(not row["costs"] for row in scale_rows):
        questions.append(clarification("costs_missing", bi("请列出各尺度承担或转移的代价，包括谁承担。", "List costs borne or transferred at each scale, including who bears them.")))
    if conflicts:
        questions.append(clarification("conflict_calibration_needed", bi("请逐项校准尺度冲突，并说明不能兼容时的暂停或退出条件。", "Calibrate each scale conflict and state pause or exit conditions when they cannot be reconciled.")))
    expires_on = context.get("expires_on")
    if not expires_on:
        questions.append(clarification("expiry_missing", bi("请设置方向的失效或复核日期，防止惯性延续。", "Set an expiry or review date for the direction to prevent unexamined continuation.")))
    supplied_triggers = as_list(context.get("triggers"))
    triggers = [{"condition": item, "source": "explicit_context"} if isinstance(item, str) else item for item in supplied_triggers]
    triggers.extend([
        {"condition": "已声明方向的实际偏离达到修正层级", "measurement": "user_defined_deviation_measure_required", "source": "engineering_operationalization"},
        {"condition": "失效日期到达且尚未完成复核", "measurement": "expires_on", "source": "engineering_operationalization"},
    ])
    data = {
        "scales_requested": scales,
        "scales_not_assessed": [item[0] for item in SCALES if item[0] not in scales],
        "scale_positions": scale_rows,
        "scale_calibration": scale_rows,
        "conflicts": conflicts,
        "conflict_detection": "incomplete" if missing_positions else "explicit_context_only",
        "aggregation": {
            "method": "recursive_calibration",
            "weighted_sum": False,
            "weighted_summation": "forbidden",
            "weighted_total": None,
            "compensation": "forbidden",
            "numeric_total": None,
            "reason": "正典公理三：多尺度意义不可通约，协调不是加权求和。",
            "canon_reference": "§4.3",
        },
        "priority_order": priorities,
        "priority_candidates": [scale_labels[scale] for scale in (priorities or scales)],
        "selected_priority": None,
        "priority_status": "provided" if priorities else "needs_clarification",
        "costs": [{"scale": row["scale"], "items": row["costs"]} for row in scale_rows],
        "provisional_direction": {
            "direction": candidate,
            "status": "provisional_pending_human_approval" if candidate else "not_selected",
            "basis": direction_basis,
            "human_approval": "pending",
            "commitment": False,
        },
        "correction_policy": [dict(item) for item in CORRECTION_LEVELS],
        "trigger_conditions": triggers,
        "triggers": triggers,
        "expires_on": expires_on,
        "automatic_execution": False,
        "canon_links": ["H7", "H8", "H9"],
    }
    return envelope(SPEC, data, questions)
