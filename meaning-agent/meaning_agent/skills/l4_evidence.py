from ..constants import D7_MODULES, ENGINEERING_FALSIFIERS, EVIDENCE_LEVELS, HYPOTHESES, PROVENANCE
from ..i18n import bi
from ..models import SkillSpec
from .common import clarification, envelope, inputs, missing_text

SPEC = SkillSpec(
    name="grade-evidence-falsification",
    description="列出 E0–E6、正典假设与证伪条件，区分用户证据声明和已核验等级，不自动授予实证等级。",
    description_en="List E0–E6, canon hypotheses, and falsification conditions; distinguish user evidence claims from verified levels without assigning empirical levels automatically.",
    layer="L4",
    input="text: str; context: dict; upstream.L1/L3: dict",
    output="evidence_items, E0–E6 reference, H1–H18, D.7, falsification_conditions",
    implementation="meaning_agent.skills.l4_evidence.run",
)

LINKED = {"H2", "H7", "H8", "H9", "H10", "H11", "H12", "H13", "H14"}


def evidence_items(context):
    supplied = context.get("evidence", context.get("sources", []))
    if isinstance(supplied, str):
        supplied = [supplied]
    if isinstance(supplied, dict):
        supplied = [{"source": key, "description": value} for key, value in supplied.items()]
    if not isinstance(supplied, list):
        supplied = []
    items = []
    for index, item in enumerate(supplied[:50]):
        if isinstance(item, dict):
            source = item.get("source") or item.get("id") or f"user_item_{index + 1}"
            description = item.get("description") or item.get("claim") or ""
            claimed = item.get("level") or item.get("claimed_level")
        else:
            source = f"user_item_{index + 1}"
            description = str(item)
            claimed = None
        items.append({
            "source": source,
            "description": description,
            "claimed_level": claimed,
            "accepted_level": None,
            "verification_status": "user_supplied_unverified",
            "claim_id": item.get("claim_id") if isinstance(item, dict) else None,
            "supplied_verified_claim": isinstance(item, dict) and item.get("verified") is True,
        })
    return items


def run(payload):
    text, context = inputs(payload)
    if not text:
        return missing_text(SPEC)
    upstream = payload.get("upstream", {})
    l3 = upstream.get("L3", {}) if isinstance(upstream, dict) else {}
    dimensions = l3.get("data", {}).get("dimensions", {}) if isinstance(l3, dict) else {}
    claims = []
    for key in ("direction", "value", "boundary"):
        dimension = dimensions.get(key, {}) if isinstance(dimensions, dict) else {}
        statement = dimension.get("statement") or dimension.get("candidates") or dimension
        claims.append({
            "dimension": key,
            "claim": statement,
            "basis": "candidate_interpretation_of_input",
            "empirical_level": None,
            "automatic_level_assignment": False,
            "verification_status": "not_independently_verified",
            "falsification": "须对照相应正典卡片或已预注册的工程条件；文本本身不能触发实证结论。",
        })
    items = evidence_items(context)
    valid_levels = {item["id"] for item in EVIDENCE_LEVELS}
    supplied_by_claim = {}
    for item in items:
        claim_id = item.get("claim_id")
        level = item.get("claimed_level")
        if isinstance(claim_id, str) and level in valid_levels:
            supplied_by_claim[claim_id] = item

    raw_statements = payload.get("statements")
    if not isinstance(raw_statements, list):
        l1 = upstream.get("L1", {}) if isinstance(upstream, dict) else {}
        separation = l1.get("data", {}).get("fact_question_separation", {}) if isinstance(l1, dict) else {}
        raw_statements = separation.get("reported_statements", []) if isinstance(separation, dict) else []
    statement_claims = []
    for index, statement in enumerate(raw_statements[:50]):
        if not isinstance(statement, dict):
            continue
        statement_claims.append({
            "claim_id": str(statement.get("id") or f"s{index + 1}")[:100],
            "claim": str(statement.get("text") or "")[:2000],
            "kind": statement.get("kind"),
            "basis": "input_statement_unverified",
        })
    if not statement_claims:
        for index, claim in enumerate(claims):
            statement_claims.append({
                "claim_id": f"d{index + 1}_{claim['dimension']}",
                "claim": claim["claim"],
                "kind": "interpretation_candidate",
                "basis": claim["basis"],
            })
    assessments = []
    for claim in statement_claims:
        supplied = supplied_by_claim.get(claim["claim_id"])
        level = supplied.get("claimed_level") if supplied else None
        assessments.append({
            **claim,
            "level": level,
            "level_source": "user_supplied_metadata" if level else "not_assigned",
            "current_empirical_status": "user_asserted_not_independently_verified" if level else "unknown",
            "automatic_level_assignment": False,
            "supplied_metadata_claims_verified": bool(supplied and supplied.get("supplied_verified_claim")),
            "independently_verified_by_this_tool": False,
        })
    falsification_plans = [{
        "claim_id": item["claim_id"],
        "falsifier": bi(
            "预先声明可推翻该主张的测量、样本、阈值与独立检验者；本工具未执行检验。",
            "Preregister the measurement, sample, threshold, and independent tester that could refute this claim; this tool has not tested it.",
        ),
        "status": "not_tested",
        "result": None,
        "requires_preregistration": True,
        "executed_by_this_tool": False,
    } for item in assessments]
    claimed_levels = context.get("evidence_claims", {})
    if isinstance(claimed_levels, dict):
        for key, value in claimed_levels.items():
            items.append({"source": f"claim:{key}", "description": "用户提供的等级声明", "claimed_level": value, "accepted_level": None, "verification_status": "requires_preregistered_evidence_review"})
    questions = []
    if not items:
        questions.append(clarification("evidence_missing", bi("请提供可复核来源、预注册方案、数据或独立复现记录；否则不能授予 E1–E6。", "Provide auditable sources, a preregistered plan, data, or independent replication records; otherwise E1–E6 cannot be assigned.")))
    else:
        questions.append(clarification("evidence_unverified", bi("谁已核验这些来源？请提供对应的预注册与检验记录。", "Who verified these sources? Provide the corresponding preregistration and test records.")))
    questions.append(clarification("falsifier_measurement_missing", bi("请说明由谁、在何种样本与测量方案下检验证伪条件。", "State who will test the falsification condition, with which sample and measurement plan.")))
    linked = [dict(item) for item in HYPOTHESES if item["id"] in LINKED]
    hypothesis_candidates = [{**item, "warning": bi(
        "这是正典假设记录，不是本工具对新主张的实证认定。",
        "This is a canon hypothesis record, not an empirical determination by this tool.",
    )} for item in linked]
    data = {
        "automatic_empirical_level": None,
        "automatic_empirical_level_claim": False,
        "level_policy": "E0–E6 描述知识状态，不是质量分数；本引擎不自动声称任何分析主张已达到某一级。",
        "framework_provenance": {"six_layer_stack_level": "E0", "meaning": "engineering_extension_not_an_empirical_result"},
        "evidence_items": items,
        "evidence_catalog": [dict(item) for item in EVIDENCE_LEVELS],
        "claims": claims,
        "claim_assessments": assessments,
        "falsification_plans": falsification_plans,
        "reference_scale": [dict(item) for item in EVIDENCE_LEVELS],
        "linked_hypotheses": linked,
        "hypothesis_candidates": hypothesis_candidates,
        "canon_hypotheses": [{**dict(item), "source": "V7.0 正典假设卡片；本处为摘要，冲突以正典为准", "level_is_recorded_not_newly_assigned": True} for item in HYPOTHESES],
        "appendix_d7": [{**dict(item), "source": "V7.0 正典附录 D.7", "not_six_layer_thresholds": True} for item in D7_MODULES],
        "falsification_conditions": {
            "canon_priority": PROVENANCE["canon"],
            "hypotheses": [dict(item) for item in HYPOTHESES],
            "appendix_d7": [dict(item) for item in D7_MODULES],
            "engineering_drafts": [{**dict(item), "requires_preregistration": True, "formal_disposition_allowed": False} for item in ENGINEERING_FALSIFIERS],
            "automatic_falsification_claim": False,
        },
    }
    return envelope(SPEC, data, questions)
