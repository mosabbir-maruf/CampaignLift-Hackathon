"""Validation tests for Model Selection (Step 15.4).

Verifies that selection.json and metadata_draft.json:
1. Exist in ml/experiments/
2. Formulate the exact pre-committed validation Qini selection rule
3. Accurately report candidate validation scores from empirical evaluation
4. Apply the 0.01 simplicity margin rule faithfully
5. Include single held-out test evaluation scores without data leakage
"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "ml" / "experiments"
SELECTION_JSON_PATH = EXPERIMENTS_DIR / "selection.json"
METADATA_DRAFT_PATH = EXPERIMENTS_DIR / "metadata_draft.json"


def test_selection_json_exists_and_valid():
    """Verify that selection.json exists and parses as valid JSON."""
    assert SELECTION_JSON_PATH.is_file(), f"selection.json missing at {SELECTION_JSON_PATH}"
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert data.get("status") == "completed"


def test_selection_json_contains_rule_and_constraints():
    """Verify pre-committed rule specifications and constraints."""
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rule = data.get("selection_rule", {})
    assert rule.get("primary_metric") == "validation_qini_score"
    assert rule.get("simplicity_margin") == 0.01
    assert "simpler Logistic T-Learner" in rule.get("tie_break_rule", "")
    assert rule.get("evaluation_cohort") == "validation_split_only"
    assert len(rule.get("constraints", [])) >= 4


def test_selection_json_contains_validation_scores():
    """Verify empirical validation scores exist for all required candidates."""
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_cands = data.get("validation_all_candidates", {})
    for cid in ["B0", "B1", "U0", "U1", "U2"]:
        assert cid in all_cands, f"Candidate {cid} missing from validation results"
        score = all_cands[cid].get("validation_qini_score")
        assert score is not None and isinstance(score, (int, float))

    rankings = data.get("validation_rankings", [])
    assert len(rankings) == 4  # Uplift candidates: U2, U1, U0, B1
    # Verify descending sort order
    scores = [r["validation_qini_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


def test_selection_json_simplicity_margin_logic():
    """Verify decision logic correctly reflects the 0.01 simplicity margin."""
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    decision = data.get("decision", {})
    winner_id = decision.get("selected_candidate_id")
    highest_id = decision.get("highest_raw_qini_candidate")
    qini_diff = decision.get("qini_difference")
    assert winner_id is not None

    if highest_id != "U0" and qini_diff < 0.01:
        assert winner_id == "U0", "Simplicity margin should have selected U0 fallback"
        assert decision.get("simplicity_margin_applied") is True
    else:
        assert winner_id == highest_id
        assert decision.get("simplicity_margin_applied") is False

    assert decision.get("refit_on_train_val") is True
    assert decision.get("refit_cohort_size") > 0


def test_selection_json_test_scores_after_single_look():
    """Verify held-out test scores exist and single test look is certified."""
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_eval = data.get("test_evaluation", {})
    assert test_eval.get("single_test_call_verified") is True

    selected_model_test = test_eval.get("selected_model", {})
    assert selected_model_test.get("candidate_id") == data["decision"]["selected_candidate_id"]
    assert selected_model_test.get("test_qini_score") is not None
    assert selected_model_test.get("test_top10_incremental_rate") is not None
    assert selected_model_test.get("n_test") > 0

    baseline_test = test_eval.get("response_baseline_b0", {})
    assert baseline_test.get("candidate_id") == "B0"
    assert baseline_test.get("test_qini_score") is not None


def test_metadata_draft_matches_selection():
    """Verify metadata draft aligns with selection results."""
    assert METADATA_DRAFT_PATH.is_file(), f"metadata_draft.json missing at {METADATA_DRAFT_PATH}"
    with open(SELECTION_JSON_PATH, "r", encoding="utf-8") as f:
        sel = json.load(f)
    with open(METADATA_DRAFT_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["selected_candidate"]["candidate_id"] == sel["decision"]["selected_candidate_id"]
    assert meta["selection_summary"]["validation_qini"] == sel["decision"]["highest_raw_qini"]
    assert meta["selection_summary"]["test_qini"] == sel["test_evaluation"]["selected_model"]["test_qini_score"]
    assert meta["training_metadata"]["single_test_look"] is True
