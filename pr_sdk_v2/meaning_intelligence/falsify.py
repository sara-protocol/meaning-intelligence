import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import yaml


NOT_PROVEN = "未证伪 ≠ 已证实"
CEILING_NOTE = "evidence_ceiling 是预注册设计上限，不是已达到的证据等级"
ANNOTATION_FIELDS = {"rater_id", "item_id", "category"}


@dataclass
class Verdict:
    status: str
    rule: str = None
    evidence_level: str = "E0"
    limitations: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)


def load_hypothesis(hid, path="hypotheses.yaml"):
    with open(path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    if not isinstance(document, dict) or not isinstance(document.get("hypotheses"), list):
        raise ValueError("hypotheses.yaml 缺少有效的 hypotheses 列表")
    for h in document["hypotheses"]:
        if isinstance(h, dict) and h.get("id") == hid:
            return h
    raise KeyError(f"假说不存在: {hid}")


def check_falsifier(hid, data=None, path="hypotheses.yaml"):
    h = load_hypothesis(hid, path)
    if h.get("status", "draft") != "registered":
        return Verdict("INCONCLUSIVE", "hypothesis_not_registered", "E0",
                       ["假说处于 draft 或未注册，未预注册"], {})
    if not data:
        return Verdict("INCONCLUSIVE", "no_data", "E0", ["未提供观测数据"], {})
    if not isinstance(data, dict):
        return _inconclusive(h, "invalid_data_schema", ["观测数据必须是对象"], data)

    for rule in h.get("inconclusive_if", []):
        matched_rule = _match(rule, data, h)
        if matched_rule:
            return _inconclusive(h, matched_rule, ["数据触发预注册 inconclusive_if 条件"], data)

    if h.get("scope") == "layer":
        return _layer(h, data)
    if h.get("scope") == "stack":
        return _stack(h, data)
    return _inconclusive(h, "unknown_scope", ["假说 scope 不受支持"], data)


def _inconclusive(h, rule, limitations, data=None):
    inputs = {"registered_evidence_ceiling": h.get("evidence_ceiling", "E0")}
    if isinstance(data, dict):
        inputs["data_keys"] = list(data.keys())
    return Verdict("INCONCLUSIVE", rule, "E0", limitations, inputs)


def _match(rule, data, h):
    if not isinstance(rule, dict):
        return "invalid_inconclusive_rule_schema"

    if "missing" in rule:
        required = rule["missing"]
        if not isinstance(required, list) or not required or not all(isinstance(k, str) for k in required):
            return "invalid_inconclusive_rule_schema"
        if set(required) <= ANNOTATION_FIELDS:
            rows = data.get("annotations")
            if not isinstance(rows, list) or not rows:
                return "missing_annotations"
            if any(not isinstance(row, dict) or any(k not in row for k in required) for row in rows):
                return "missing_annotation_fields"
        elif any(k not in data for k in required):
            return "missing_required_fields"

    if "n" in rule:
        threshold = _parse_count_bound(rule["n"])
        if threshold is None or not _is_count(data.get("n")):
            return "invalid_n"
        if data["n"] < threshold:
            return "insufficient_n"

    if "n_raters" in rule:
        threshold = _parse_count_bound(rule["n_raters"])
        if threshold is None or not _is_count(data.get("n_raters")):
            return "invalid_n_raters"
        if data["n_raters"] < threshold:
            return "insufficient_n_raters"

    if rule.get("metric_not_observed") is True and not _metric_data_available(h, data):
        return "metric_not_observed"
    return None


def _parse_count_bound(spec):
    if not isinstance(spec, str) or not spec.startswith("<"):
        return None
    try:
        value = int(spec[1:].strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _metric_data_available(h, data):
    if h.get("id") != "L3-H1" or data.get("metric_level") != "nominal":
        return False
    rows = data.get("annotations")
    return (isinstance(rows, list) and bool(rows)
            and all(isinstance(row, dict) and ANNOTATION_FIELDS <= row.keys() for row in rows))


def _layer(h, data):
    if h.get("id") != "L3-H1":
        return _unsupported(h)

    metric = h.get("metric")
    threshold = h.get("threshold")
    analysis = h.get("analysis")
    if not isinstance(metric, dict) or not isinstance(threshold, dict) or not isinstance(analysis, dict):
        return _unsupported(h)
    if (metric.get("name") != "krippendorff_alpha"
            or metric.get("direction") != "increase"
            or analysis.get("method") != "alpha_with_bootstrap"
            or "max_alpha" in threshold):
        return _unsupported(h)

    min_alpha = threshold.get("min_alpha")
    if (isinstance(min_alpha, bool) or not isinstance(min_alpha, (int, float))
            or not math.isfinite(min_alpha) or not 0 <= min_alpha <= 1):
        return _unsupported(h)
    return _evaluate_nominal_alpha(h, data, float(min_alpha))


def _evaluate_nominal_alpha(h, data, min_alpha):
    if data.get("metric_level") != "nominal":
        return _inconclusive(
            h, "unsupported_annotation_metric_level",
            ["仅支持显式 metric_level='nominal' 的原始标注；启发式分桶不是测量数据"], data)

    validated, error = _validate_annotations(data.get("annotations"))
    if error:
        return _inconclusive(h, error, ["标注数据不符合已验证的原始数据模式"], data)
    items, raters = validated

    if len(raters) != data.get("n_raters"):
        return _inconclusive(h, "rater_count_mismatch",
                             ["声明的 n_raters 与原始标注中的唯一标注者数不一致"], data)

    # L3-H1 preregisters exclusion of items annotated by fewer than two raters.
    pairable_items = [categories for categories in items.values() if len(categories) >= 2]
    excluded_items = len(items) - len(pairable_items)
    if not pairable_items:
        return _inconclusive(h, "insufficient_pairable_items",
                             ["没有至少两名标注者共同标注的 item"], data)

    alpha = _krippendorff_alpha_nominal(pairable_items)
    if alpha is None:
        return _inconclusive(h, "undefined_krippendorff_alpha",
                             ["可配对数据只有一个类别，期望分歧为零，alpha 未定义"], data)

    inputs = {
        "data_keys": list(data.keys()),
        "registered_evidence_ceiling": h.get("evidence_ceiling", "E0"),
        "observed_alpha": alpha,
        "registered_min_alpha": min_alpha,
        "pairable_items": len(pairable_items),
        "excluded_items_lt_2_raters": excluded_items,
    }
    limitations = [
        "仅计算预注册阈值所需的名义 alpha 点估计；未执行 bootstrap 或置信区间",
        "SDK 验证数据结构与计算，不能验证观测数据来源的真实性",
        CEILING_NOTE,
    ]
    if alpha < min_alpha:
        return Verdict("FALSIFIED", "krippendorff_alpha_below_min_alpha", "E0",
                       limitations, inputs)
    limitations.insert(0, NOT_PROVEN)
    return Verdict("NOT_FALSIFIED", "krippendorff_alpha_meets_min_alpha", "E0",
                   limitations, inputs)


def _validate_annotations(rows):
    if not isinstance(rows, list) or not rows:
        return None, "missing_annotations"
    items = defaultdict(list)
    raters = set()
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not ANNOTATION_FIELDS <= row.keys():
            return None, "invalid_annotation_schema"
        rater_id, item_id, category = row["rater_id"], row["item_id"], row["category"]
        if not all(_valid_label(value) for value in (rater_id, item_id, category)):
            return None, "invalid_annotation_schema"
        pair = (rater_id, item_id)
        if pair in seen:
            return None, "duplicate_rater_item"
        seen.add(pair)
        raters.add(rater_id)
        items[item_id].append(category)
    return (items, raters), None


def _valid_label(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, int)


def _krippendorff_alpha_nominal(items):
    coincidence = defaultdict(Counter)
    marginals = Counter()
    total = 0
    for categories in items:
        counts = Counter(categories)
        m = len(categories)
        total += m
        for category, n_category in counts.items():
            for other, n_other in counts.items():
                numerator = (n_category * (n_category - 1) if category == other
                             else n_category * n_other)
                coincidence[category][other] += numerator / (m - 1)
    for category, row in coincidence.items():
        marginals[category] = sum(row.values())

    observed_disagreement = sum(
        count for category, row in coincidence.items()
        for other, count in row.items() if category != other
    ) / total
    expected_disagreement = sum(
        marginals[category] * marginals[other]
        for category in marginals for other in marginals if category != other
    ) / (total * (total - 1))
    if expected_disagreement == 0:
        return None
    return 1 - observed_disagreement / expected_disagreement


def _unsupported(h, extra_limitations=None):
    analysis = h.get("analysis") if isinstance(h.get("analysis"), dict) else {}
    method = analysis.get("method", "unspecified")
    limitations = [
        f"当前 SDK 未实现该假说预注册分析（{method}）的完整确定性评估",
        "不接受以 n、自报效应量/p 值或表单完整度替代原始数据与预注册规则",
    ]
    limitations.extend(extra_limitations or [])
    limitations.extend([NOT_PROVEN, CEILING_NOTE])
    return _inconclusive(h, "unsupported_threshold_evaluation", limitations, None)


def _stack(h, data):
    return _unsupported(h, [
        "S-H1 需要按 input_id 配对的原始数据、效应量、Wilcoxon 符号秩检验和 Holm 校正；当前未实现",
    ])
