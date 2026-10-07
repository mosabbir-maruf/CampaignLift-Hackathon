"""Unit tests for Segment and Oracle Report module.

Verifies:
1. Acceptance criteria: Run without hidden file produces Qini block with synthetic_oracle=None.
2. Acceptance criteria: Run with hidden file produces Qini block AND labels oracle block 'synthetic_oracle'.
3. Band derivation functions: activity_band (0, 1-4, 5+) and prior_exposure_band (0, 1-2, 3+).
4. Demographic & behavioral slices: age_band, region_code, kyc_level, activity_band, prior_exposure_band.
5. Strict anti-leakage: feeding true_uplift inside val_df raises ForbiddenColumnError.
6. JSON serialization and saving to disk.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from campaignlift_ml.data import ForbiddenColumnError, load_train_val
from campaignlift_ml.report import (
    derive_activity_band,
    derive_prior_exposure_band,
    generate_validation_report,
    run_smoke_validation_report,
)
from campaignlift_ml.uplift import train_logistic_t_learner

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"
HIDDEN_FILE = FIXTURE_DIR / "hidden_uplift.json"


def test_band_derivations():
    """Verify scalar and series derivation of activity and exposure bands."""
    # Activity band: 0, 1-4, 5+
    assert derive_activity_band(0) == "0"
    assert derive_activity_band(1) == "1-4"
    assert derive_activity_band(4) == "1-4"
    assert derive_activity_band(5) == "5+"
    assert derive_activity_band(12) == "5+"

    # Prior exposure band: 0, 1-2, 3+
    assert derive_prior_exposure_band(0) == "0"
    assert derive_prior_exposure_band(1) == "1-2"
    assert derive_prior_exposure_band(2) == "1-2"
    assert derive_prior_exposure_band(3) == "3+"
    assert derive_prior_exposure_band(10) == "3+"

    # Series behavior
    s_act = pd.Series([0, 2, 7])
    res_act = derive_activity_band(s_act)
    assert list(res_act) == ["0", "1-4", "5+"]

    s_exp = pd.Series([0, 1, 5])
    res_exp = derive_prior_exposure_band(s_exp)
    assert list(res_exp) == ["0", "1-2", "3+"]


def test_validation_report_without_oracle():
    """Acceptance criteria: Run without hidden file still produces the Qini block."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    learner = train_logistic_t_learner(train_df)
    preds = learner.predict_uplift(val_df)

    report = generate_validation_report(
        val_df=val_df,
        uplift_preds=preds.uplift,
        p_treat=preds.p_treat,
        candidate_id="U0",
        model_name="logistic_t_learner",
        hidden_uplift_path=None,  # No oracle file
    )

    # 1. Overall Qini block must be present
    assert "overall_metrics" in report
    overall = report["overall_metrics"]
    assert "qini_score" in overall
    assert np.isfinite(overall["qini_score"])
    assert overall["n_eval"] == len(val_df)

    # 2. Slices must be present
    assert "segments" in report
    segments = report["segments"]
    for slice_name in ["age_band", "region_code", "kyc_level", "activity_band", "prior_exposure_band"]:
        assert slice_name in segments, f"Missing slice: {slice_name}"
        assert len(segments[slice_name]) > 0

    # 3. Oracle block must be None
    assert report["synthetic_oracle"] is None


def test_validation_report_with_oracle():
    """Acceptance criteria: Run with hidden file labels the oracle block 'synthetic_oracle'."""
    assert HIDDEN_FILE.exists(), f"Missing fixture oracle file: {HIDDEN_FILE}"

    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    learner = train_logistic_t_learner(train_df)
    preds = learner.predict_uplift(val_df)

    report = generate_validation_report(
        val_df=val_df,
        uplift_preds=preds.uplift,
        p_treat=preds.p_treat,
        candidate_id="U0",
        model_name="logistic_t_learner",
        hidden_uplift_path=HIDDEN_FILE,  # Explicit oracle file
    )

    # 1. Overall Qini block still present
    assert "overall_metrics" in report
    assert np.isfinite(report["overall_metrics"]["qini_score"])

    # 2. Oracle block is populated and labeled 'synthetic_oracle'
    assert report["synthetic_oracle"] is not None
    oracle = report["synthetic_oracle"]
    assert oracle["label"] == "synthetic_oracle"
    assert "Synthetic benchmark metric only" in oracle["caveat"]
    assert "spearman_rank_correlation" in oracle
    assert -1.0 <= oracle["spearman_rank_correlation"] <= 1.0
    assert "mean_true_uplift_overall" in oracle
    assert "mean_true_uplift_top_decile_predicted_uplift" in oracle


def test_report_refuses_leaked_forbidden_columns():
    """Anti-leakage: feeding true_uplift inside val_df raises ForbiddenColumnError."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    corrupted_val = val_df.copy()
    corrupted_val["true_uplift"] = 0.05

    with pytest.raises(ForbiddenColumnError, match="CRITICAL CAUSAL LEAKAGE"):
        generate_validation_report(
            val_df=corrupted_val,
            uplift_preds=np.zeros(len(val_df)),
        )


def test_report_writer_saves_json(tmp_path):
    """Report saves valid JSON to output_path if provided."""
    out_file = tmp_path / "val_report.json"
    report = run_smoke_validation_report(
        dataset_dir=FIXTURE_DIR,
        include_oracle=True,
        output_path=out_file,
    )

    assert out_file.exists()
    with out_file.open("r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["candidate_id"] == "U0"
    assert "overall_metrics" in loaded
    assert loaded["synthetic_oracle"]["label"] == "synthetic_oracle"


def test_fairness_slice_evaluation_metadata(tmp_path):
    """Verify that Fairness Slice Evaluation produces expected metadata and all 5 slices."""
    out_file = tmp_path / "fairness_slice_evaluation.json"
    report = run_smoke_validation_report(
        dataset_dir=FIXTURE_DIR,
        include_oracle=True,
        output_path=out_file,
        run_id="run_fairness_slice_fixture_v1",
    )

    assert report["evaluation_name"] == "Fairness Slice Evaluation"
    assert report["run_id"] == "run_fairness_slice_fixture_v1"
    assert report["row_count"] == 23
    assert report["population_name"] == "fixture_v1"

    # All five required slices must be present
    required_slices = [
        "age_band",
        "region_code",
        "kyc_level",
        "activity_band",
        "prior_exposure_band",
    ]
    for s in required_slices:
        assert s in report["segments"], f"Missing slice: {s}"
        assert len(report["segments"][s]) > 0, f"Empty slice: {s}"

    # Verify JSON file on disk matches
    assert out_file.exists()
    with out_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["evaluation_name"] == "Fairness Slice Evaluation"
    assert data["run_id"] == "run_fairness_slice_fixture_v1"
    assert data["row_count"] == 23

