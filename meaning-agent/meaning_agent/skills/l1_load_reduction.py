"""L1: separate assertions from questions and expose text structure."""

import re
from collections import Counter

from ..i18n import bi
from ..models import SkillSpec
from .common import detect_language, envelope, inputs, missing_text, unique

SPEC = SkillSpec(
    name="reduce-cognitive-load",
    description="分离文本中的陈述与待决问题，抽取关键结构和约束，并保留未验证标记。",
    description_en="Separate assertions from open questions, extract structure and constraints, and retain unverified markers.",
    layer="L1",
    input="text: str; context: dict",
    output="reported_statements, questions, key_structure, constraints, compression",
    implementation="meaning_agent.skills.l1_load_reduction.run",
)

CUE_TERMS = (
    "认知负荷", "核心意义", "方向", "价值", "边界", "证据", "证伪", "尺度", "冲突",
    "元认知", "主动归零", "归零", "决策", "数据", "来源", "时间", "成本", "风险",
    "人类", "组织", "个人", "城市", "国家", "安全", "健康", "信任", "公平", "自主",
    "责任", "目标", "问题", "事实", "假设", "模型", "智能", "意义", "专业判断",
    "evidence", "falsification", "value", "boundary", "scale", "conflict", "risk",
    "cost", "decision", "direction", "humanity", "organization", "individual",
)
STOPWORDS = {
    "我们", "你们", "他们", "这个", "那个", "这些", "那些", "可以", "需要", "进行",
    "通过", "因为", "所以", "但是", "如果", "以及", "并且", "没有", "一个", "一种",
    "什么", "如何", "是否", "为什么", "the", "and", "that", "this", "with", "from",
    "should", "would", "could", "there", "their", "about",
}
QUESTION_START = re.compile(r"^(?:为什么|如何|是否|什么|哪|谁|怎么|能否|可否|\b(?:why|how|what|whether|who|can|should)\b)", re.I)
DIRECTIVE = re.compile(r"应该|应当|必须|建议|需要|希望|决定|选择|禁止|不得|优先|\b(?:should|must|recommend|need|choose|decide|shall)\b", re.I)
CONSTRAINT = re.compile(r"必须|不得|禁止|边界|预算|期限|至少|最多|仅限|截止|\b(?:must|never|only|limit|deadline|budget)\b", re.I)
VALUE = re.compile(r"价值|意义|重要|值得|公平|健康|安全|信任|幸福|效用|内在|关系|\b(?:value|worth|fair|safe|trust|utility|wellbeing)\b", re.I)
REPORTED = re.compile(r"显示|发现|报告|记录|据|达到|占|导致|是|有|数据|研究|调查|\b(?:report|show|found|data|study|according|caused)\b", re.I)


def split_sentences(text):
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+|(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [part.strip() for part in parts if part.strip()]


def key_terms(text):
    counts = Counter()
    lowered = text.lower()
    for term in CUE_TERMS:
        count = lowered.count(term.lower())
        if count:
            counts[term] += count
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,12}", text):
        token = token.strip()
        if token.lower() in STOPWORDS or token in STOPWORDS:
            continue
        counts[token] += 1
    return sorted(counts, key=lambda item: (-counts[item], -len(item), item))[:10]


def classify(sentence):
    if DIRECTIVE.search(sentence):
        return "directive_or_recommendation"
    if VALUE.search(sentence):
        return "value_statement"
    if REPORTED.search(sentence) or re.search(r"\d", sentence):
        return "empirical_claim_unverified"
    return "reported_statement"


def run(payload):
    text, context = inputs(payload)
    if not text:
        return missing_text(SPEC)
    language = detect_language(text)
    sentences = split_sentences(text)
    questions = [item for item in sentences if "?" in item or "？" in item or QUESTION_START.search(item)]
    question_set = set(questions)
    statements = []
    for index, sentence in enumerate(sentences):
        if sentence in question_set:
            continue
        statements.append({
            "id": f"s{index + 1}",
            "text": sentence[:1200],
            "kind": classify(sentence),
            "verification": "unverified",
            "empirical_status": "unknown",
            "source": "input_text_only",
        })
    terms = key_terms(text)
    nodes = [{
        "id": f"n{index + 1}", "label": term,
        "mentions": text.lower().count(term.lower()),
        "provenance": "lexical_heuristic",
    } for index, term in enumerate(terms)]
    relations = []
    for left_index, left in enumerate(terms):
        for right in terms[left_index + 1:]:
            if any(left in sentence and right in sentence for sentence in sentences):
                relations.append({"from": left, "to": right, "relation": "co_occurs_in_text", "inferred_causality": False})
            if len(relations) >= 16:
                break
        if len(relations) >= 16:
            break
    constraints = unique(sentence[:600] for sentence in sentences if CONSTRAINT.search(sentence))
    core = [item["text"] for item in statements[:3]]
    summary = "；".join(core)[:300]
    data = {
        "title": bi("事实 / 问题分离", "Fact / question separation"),
        "fact_question_separation": {
            "reported_statements": statements,
            "open_questions": [{"id": f"q{index + 1}", "text": question} for index, question in enumerate(questions)],
            "warning": bi(
                "陈述仅代表输入文本的断言，不是已核实事实。",
                "Statements are assertions from the input, not verified facts.",
            ),
        },
        "key_structure": {
            "nodes": nodes,
            "relations": relations,
            "method": "deterministic_lexical_cooccurrence",
            "causality_inferred": False,
        },
        "critical_constraints": constraints,
        "controlled_restatement": {"text": summary, "language": language, "method": "first_three_non_questions"},
        "compression": {
            "original_characters": len(text),
            "restatement_limit": 300,
            "omitted_statement_count": max(0, len(statements) - 3),
            "source_text_retained": True,
        },
        "source_text": text,
        "provenance_available": bool(context.get("source") or context.get("sources")),
    }
    return envelope(SPEC, data)
