import re

from ..i18n import bi
from ..models import SkillSpec
from .common import clarification, envelope, inputs, missing_text, unique

SPEC = SkillSpec(
    name="map-direction-value-boundary",
    description="沿方向、价值、边界三维度和连续意义光谱带生成候选意义结构，不把候选当承诺。",
    description_en="Generate candidate meaning structures along direction, value, and boundary dimensions and a continuous spectrum without treating candidates as commitments.",
    layer="L3",
    input="text: str; context: dict; upstream.L1: dict",
    output="dimensions(direction/value/boundary), spectrum_position, clarification_questions",
    implementation="meaning_agent.skills.l3_meaning_generation.run",
)

DIRECTIVE = re.compile(r"应该|应当|必须|建议|需要|希望|决定|选择|优先|值得|应|\b(?:should|must|recommend|need|choose|decide|prioritize|worth)\b", re.I)
ABSTRACT = re.compile(r"人类|文明|长期|终极|原则|战略|使命|未来|世代|\b(?:humanity|long.term|mission|principle|strategy|future)\b", re.I)
CONCRETE = re.compile(r"今天|本次|当前|立即|此刻|个人|具体|本周|当日|\b(?:today|now|immediate|this week|specific)\b", re.I)
TEMPORAL = re.compile(r"今天|本周|本月|今年|明年|短期|长期|十年|\d+\s*(?:天|月|年)|\b(?:today|month|year|decade|short.term|long.term)\b", re.I)


def first_directive(text):
    for sentence in re.split(r"(?<=[。！？!?；;])\s*|\n+", text):
        if DIRECTIVE.search(sentence):
            return sentence.strip()[:600]
    return None


def spectrum(text, context):
    supplied = context.get("spectrum_position")
    if isinstance(supplied, (int, float)) and not isinstance(supplied, bool) and 0 <= supplied <= 100:
        return {"position": supplied, "segment": "upper_meta_leaning" if supplied >= 67 else "lower_situational_leaning" if supplied <= 33 else "middle_band", "status": "user_supplied_not_measurement", "method": "explicit_context", "abstraction": None, "time_horizon": context.get("time_horizon"), "frequency": context.get("frequency")}
    abstract_count = len(ABSTRACT.findall(text))
    concrete_count = len(CONCRETE.findall(text))
    if not abstract_count and not concrete_count:
        return {"position": None, "segment": "unknown", "status": "needs_clarification", "method": "no_reliable_cue", "abstraction": None, "time_horizon": context.get("time_horizon"), "frequency": context.get("frequency")}
    position = max(0, min(100, 50 + 18 * (abstract_count - concrete_count)))
    return {
        "position": position,
        "segment": "upper_meta_leaning" if position >= 67 else "lower_situational_leaning" if position <= 33 else "middle_band",
        "status": "candidate_heuristic",
        "method": "lexical_cue_not_validated_measurement",
        "abstraction": "high_cue" if position >= 67 else "low_cue" if position <= 33 else "mixed_cue",
        "time_horizon": context.get("time_horizon") or (TEMPORAL.search(text).group(0) if TEMPORAL.search(text) else None),
        "frequency": context.get("frequency"),
        "uncertainty": "high",
    }


def run(payload):
    text, context = inputs(payload)
    if not text:
        return missing_text(SPEC)
    questions = []
    direction = context.get("direction") if isinstance(context.get("direction"), str) else None
    direction = direction.strip() if direction else first_directive(text)
    direction_basis = "explicit_context" if isinstance(context.get("direction"), str) and context.get("direction", "").strip() else "text_directive_candidate"
    if not direction:
        direction = None
        direction_basis = "not_provided"
        questions.append(clarification("direction_missing", bi("这件事要把谁带向哪里？反方向是什么？", "Who should this move, in which direction, and what is the opposite direction?")))
    supplied_value_types = context.get("value_types", [])
    if not isinstance(supplied_value_types, (list, tuple, set)):
        supplied_value_types = []
    value_cues = []
    for key, label, pattern in (
        ("utility", "效用价值", r"效率|成本|效用|收益|产出|\b(?:efficient|cost|utility|output)\b"),
        ("intrinsic", "内在价值", r"自主|尊严|健康|成长|意义|公平|\b(?:autonomy|dignity|health|growth|meaning|fairness)\b"),
        ("relational", "关系价值", r"信任|关系|关怀|合作|共同体|\b(?:trust|relationship|care|cooperation|community)\b"),
    ):
        if re.search(pattern, text, re.I) or key in supplied_value_types:
            value_cues.append({"type": key, "label": label, "status": "candidate_not_weighted"})
    if not value_cues:
        questions.append(clarification("value_missing", bi("它主要满足效用、内在还是关系价值？请说明受益者与代价。", "Is the main value utility, intrinsic, or relational? Identify beneficiaries and costs.")))
    supplied_boundaries = context.get("boundaries", {})
    if not isinstance(supplied_boundaries, dict):
        supplied_boundaries = {}
    temporal = supplied_boundaries.get("temporal") or context.get("time_horizon")
    spatial = supplied_boundaries.get("spatial") or context.get("spatial_boundary")
    relational = supplied_boundaries.get("relational") or context.get("relational_boundary")
    if not temporal and TEMPORAL.search(text):
        temporal = TEMPORAL.search(text).group(0)
    boundary_cues = [item[:300] for item in re.split(r"(?<=[。！？!?；;])\s*|\n+", text) if re.search(r"边界|期限|预算|仅限|不得|禁止|至少|最多|\b(?:boundary|limit|deadline|only|must not)\b", item, re.I)]
    for code, label, label_en, value in (("temporal_boundary_missing", "时间", "temporal", temporal), ("spatial_boundary_missing", "空间", "spatial", spatial), ("relational_boundary_missing", "关系", "relational", relational)):
        if not value:
            questions.append(clarification(code, bi(f"请明确{label}边界；不要用默认值代替用户条件。", f"Specify the {label_en} boundary; do not substitute a default for the user's conditions.")))
    position = spectrum(text, context)
    if position["status"] == "needs_clarification":
        questions.append(clarification("spectrum_missing", bi("请提供抽象程度、时间跨度或使用频率，以定位连续光谱带。", "Provide abstraction level, time horizon, or usage frequency to position the continuous spectrum.")))
    directions = ([{"text": direction, "basis": direction_basis, "status": "candidate_not_commitment"}] if direction else [])
    values = [{"type": item["type"], "text": item["label"], "status": item["status"]} for item in value_cues]
    supplied_boundary_items = [
        {"kind": kind, "text": value}
        for kind, value in (("temporal", temporal), ("spatial", spatial), ("relational", relational))
        if value
    ]
    data = {
        "dimension_system": "direction_value_boundary",
        "dimensions": {
            "direction": {"question": "这件事把我们带向哪里？", "statement": direction, "opposite": context.get("opposite_direction"), "basis": direction_basis, "status": "candidate" if direction else "unknown"},
            "value": {"question": "它满足什么价值，对谁有价值？", "candidates": value_cues, "weights": None, "status": "candidate" if value_cues else "unknown"},
            "boundary": {"question": "时间、空间、关系边界在哪里？", "temporal": temporal, "spatial": spatial, "relational": relational, "text_cues": boundary_cues, "status": "partial" if temporal or spatial or relational else "unknown"},
        },
        "directions": directions,
        "values": values,
        "boundaries": {
            "hard": [{"text": item, "source": "explicit_constraint_cue"} for item in boundary_cues],
            "soft": supplied_boundary_items,
            "missing": [label for label, value in (("temporal", temporal), ("spatial", spatial), ("relational", relational)) if not value],
        },
        "spectrum": {
            **position,
            "model": "canon_8_1_continuous_band",
            "range": "0 = situational/concrete/short/high-frequency; 100 = meta/abstract/long/low-frequency",
            "fixed_three_drawers": False,
            "not_the_four_dimension_bs_model": True,
        },
        "continuous_spectrum": {
            "minimum": 0,
            "maximum": 100,
            "heuristic_position": position["position"],
            "selected_position": None,
            "position_source": (
                "user_context"
                if position["method"] == "explicit_context"
                else "no_reliable_cue"
                if position["position"] is None
                else "three_signal_heuristic"
            ),
            "position_is_measurement": False,
            "human_selection_required": True,
            "range": "0 = situational/concrete/short/high-frequency; 100 = meta/abstract/long/low-frequency",
            "fixed_three_drawers": False,
        },
        "selected_direction": None,
        "approval_status": "pending_human",
        "candidate_not_commitment": True,
    }
    return envelope(SPEC, data, questions)
