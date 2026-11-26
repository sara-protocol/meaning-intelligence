from copy import deepcopy
from pathlib import Path
import tempfile

import yaml

from meaning_intelligence.falsify import check_falsifier


ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES_PATH = ROOT / "hypotheses.yaml"
RESULTS = []


def t(name, got, expect):
    try:
        assert got == expect, f"{name}: got {got!r}, expected {expect!r}"
    except AssertionError as error:
        RESULTS.append(False)
        print(f"[FAIL] {error}")
        return False
    RESULTS.append(True)
    print(f"[OK] {name}: {got}")
    return True


def _write_registered_fixture(path):
    with HYPOTHESES_PATH.open(encoding="utf-8") as f:
        document = yaml.safe_load(f)
    by_id = {h["id"]: h for h in document["hypotheses"]}
    registered = []
    for hid in ("L2-H1", "L3-H1", "S-H1"):
        hypothesis = deepcopy(by_id[hid])
        hypothesis["status"] = "registered"
        registered.append(hypothesis)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump({"hypotheses": registered}, f, allow_unicode=True, sort_keys=False)
    return path


def _annotations(rows):
    return {
        "metric_level": "nominal",
        "n_raters": len({row[0] for row in rows}),
        "annotations": [
            {"rater_id": rater, "item_id": item, "category": category}
            for rater, item, category in rows
        ],
    }


def _run_tests(registered_path):
    draft = check_falsifier("S-H1", None, path=str(HYPOTHESES_PATH))
    t("S-H1 draft status", draft.status, "INCONCLUSIVE")
    t("S-H1 draft rule", draft.rule, "hypothesis_not_registered")
    t("S-H1 draft remains E0", draft.evidence_level, "E0")

    no_data = check_falsifier("L1-H1", None, path=str(HYPOTHESES_PATH))
    t("L1-H1 no-data status", no_data.status, "INCONCLUSIVE")
    t("L1-H1 no-data rule", no_data.rule, "no_data")
    t("L1-H1 empty data remains no_data", check_falsifier("L1-H1", {}, path=str(HYPOTHESES_PATH)).rule, "no_data")

    inadequate = check_falsifier(
        "L1-H1", {"n": 5, "treatment_data": [1], "control_data": [2]},
        path=str(HYPOTHESES_PATH))
    t("L1-H1 inadequate sample is inconclusive", inadequate.status, "INCONCLUSIVE")
    t("L1-H1 inadequate sample rule", inadequate.rule, "insufficient_n")

    fabricated = check_falsifier(
        "L1-H1",
        {"n": 100, "treatment_data": [1], "control_data": [2],
         "effect_size": 0.9, "p_value": 0.99, "threshold_met": True},
        path=str(HYPOTHESES_PATH))
    t("L1-H1 fabricated summary cannot be not-falsified", fabricated.status, "INCONCLUSIVE")
    t("L1-H1 fabricated summary rule", fabricated.rule, "metric_not_observed")
    t("L1-H1 unsupported evaluation remains E0", fabricated.evidence_level, "E0")

    unsupported = check_falsifier(
        "L2-H1",
        {"n": 100, "treatment_data": [1], "control_data": [2],
         "effect_size": 0.9, "p_value": 0.01},
        path=str(registered_path))
    t("Unsupported layer rule is inconclusive", unsupported.status, "INCONCLUSIVE")
    t("Unsupported layer rule is explicit", unsupported.rule, "unsupported_threshold_evaluation")

    stack = check_falsifier(
        "S-H1",
        {"n": 40, "full_stack_data": [1], "ablation_data": [2],
         "effect_size": 0.5, "p_value": 0.01},
        path=str(registered_path))
    t("Fabricated stack data cannot be not-falsified", stack.status, "INCONCLUSIVE")
    t("Fabricated stack data is not evidence", stack.evidence_level, "E0")

    alpha_summary = check_falsifier(
        "L3-H1", {"n_raters": 2, "metric_level": "nominal", "alpha": 0.99},
        path=str(registered_path))
    t("Self-reported alpha cannot be not-falsified", alpha_summary.status, "INCONCLUSIVE")
    t("Self-reported alpha rule", alpha_summary.rule, "missing_annotations")

    agreeing = _annotations([
        ("r1", "i1", "A"), ("r2", "i1", "A"),
        ("r1", "i2", "B"), ("r2", "i2", "B"),
    ])
    supported = check_falsifier("L3-H1", agreeing, path=str(registered_path))
    t("Supported alpha threshold can be not-falsified", supported.status, "NOT_FALSIFIED")
    t("Supported alpha threshold rule", supported.rule, "krippendorff_alpha_meets_min_alpha")
    t("Supported alpha is calculated from raw rows", supported.inputs["observed_alpha"], 1.0)
    t("Supported alpha remains E0", supported.evidence_level, "E0")
    t("Not-falsified retains non-proof warning", any("未证伪 ≠ 已证实" in x for x in supported.limitations), True)

    disagreeing = _annotations([
        ("r1", "i1", "A"), ("r2", "i1", "B"),
        ("r1", "i2", "A"), ("r2", "i2", "B"),
    ])
    falsified = check_falsifier("L3-H1", disagreeing, path=str(registered_path))
    t("Supported alpha threshold can falsify", falsified.status, "FALSIFIED")
    t("Falsified alpha rule", falsified.rule, "krippendorff_alpha_below_min_alpha")
    t("Falsified verdict remains E0", falsified.evidence_level, "E0")

    one_rater = check_falsifier(
        "L3-H1", _annotations([("r1", "i1", "A")]), path=str(registered_path))
    t("One rater is inadequate", one_rater.status, "INCONCLUSIVE")
    t("One rater rule", one_rater.rule, "insufficient_n_raters")

    no_pairs = check_falsifier(
        "L3-H1", _annotations([("r1", "i1", "A"), ("r2", "i2", "B")]),
        path=str(registered_path))
    t("No pairable items is inadequate", no_pairs.status, "INCONCLUSIVE")
    t("No pairable items rule", no_pairs.rule, "insufficient_pairable_items")

    no_variation = check_falsifier(
        "L3-H1", _annotations([("r1", "i1", "A"), ("r2", "i1", "A")]),
        path=str(registered_path))
    t("Undefined alpha cannot be not-falsified", no_variation.status, "INCONCLUSIVE")
    t("Undefined alpha rule", no_variation.rule, "undefined_krippendorff_alpha")

    mismatch = deepcopy(agreeing)
    mismatch["n_raters"] = 3
    mismatch_verdict = check_falsifier("L3-H1", mismatch, path=str(registered_path))
    t("Rater count mismatch is rejected", mismatch_verdict.status, "INCONCLUSIVE")
    t("Rater count mismatch rule", mismatch_verdict.rule, "rater_count_mismatch")

    duplicate = _annotations([
        ("r1", "i1", "A"), ("r1", "i1", "B"), ("r2", "i2", "A"),
    ])
    duplicate_verdict = check_falsifier("L3-H1", duplicate, path=str(registered_path))
    t("Duplicate rater-item rows are rejected", duplicate_verdict.rule, "duplicate_rater_item")

    draft_l3 = check_falsifier("L3-H1", agreeing, path=str(HYPOTHESES_PATH))
    t("Draft hypothesis cannot evaluate a threshold", draft_l3.status, "INCONCLUSIVE")
    t("Draft L3-H1 rule", draft_l3.rule, "hypothesis_not_registered")

    with registered_path.open(encoding="utf-8") as f:
        invalid_document = yaml.safe_load(f)
    for hypothesis in invalid_document["hypotheses"]:
        if hypothesis["id"] == "L3-H1":
            hypothesis["threshold"]["min_alpha"] = "not-a-number"
    with registered_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(invalid_document, f, allow_unicode=True, sort_keys=False)
    invalid_threshold = check_falsifier("L3-H1", agreeing, path=str(registered_path))
    t("Invalid registered threshold is inconclusive", invalid_threshold.status, "INCONCLUSIVE")
    t("Invalid registered threshold rule", invalid_threshold.rule, "unsupported_threshold_evaluation")


def main():
    try:
        with tempfile.TemporaryDirectory(prefix="mi-falsify-tests-") as directory:
            registered_path = _write_registered_fixture(Path(directory) / "hypotheses.yaml")
            _run_tests(registered_path)
    except Exception as error:
        RESULTS.append(False)
        print(f"[FAIL] 测试执行异常: {type(error).__name__}: {error}")

    passed = sum(RESULTS)
    failed = len(RESULTS) - passed
    print(f"\nSUMMARY: {passed}/{len(RESULTS)} assertions passed; {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
