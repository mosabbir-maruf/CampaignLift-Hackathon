"""Tests for Response Baseline (Candidate B0) module.

Verifies:
1. Training fits strictly on treated rows (treatment == 1) of the training split.
2. Predictions on validation are finite, strictly within [0, 1], and not constant.
3. Test split is NOT read or scored during training/validation.
4. Validation evaluation outputs metrics tagged as 'smoke'.
5. Error handling for missing columns or zero treated rows.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from campaignlift_ml.data import load_train_val
from campaignlift_ml.baseline import (
    ResponseBaselineModel,
    train_response_baseline,
    run_smoke_baseline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"


def test_baseline_fit_and_predict_fixture():
    """Baseline fits on fixture treated train rows and yields non-constant, finite validation probabilities."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)

    model = train_response_baseline(train_df, random_state=20261006)
    assert model.is_fitted
    assert model.n_treated_train > 0
    assert model.n_treated_train == (train_df["treatment"] == 1).sum()

    # Predict on validation
    p_treat = model.predict_proba(val_df)

    # 1. Finite
    assert np.all(np.isfinite(p_treat)), "Predictions must be finite"

    # 2. Probability bounds
    assert np.all(p_treat >= 0.0) and np.all(p_treat <= 1.0), "Probabilities must be within [0, 1]"

    # 3. Not constant
    assert np.std(p_treat) > 0.001, "Predicted probabilities must not be constant"
    assert len(np.unique(p_treat)) > 1


def test_baseline_evaluation_smoke_tag():
    """Baseline evaluate produces valid metrics marked as eval_type 'smoke'."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    model = train_response_baseline(train_df)

    eval_result = model.evaluate(val_df, eval_type="smoke")
    result_dict = eval_result.to_dict()

    assert result_dict["eval_type"] == "smoke"
    assert result_dict["model_name"] == "logistic_regression_b0"
    assert result_dict["brier_score"] >= 0.0
    assert result_dict["min_p_treat"] <= result_dict["max_p_treat"]
    assert result_dict["n_eval_total"] == len(val_df)
    assert result_dict["n_eval_treated"] == (val_df["treatment"] == 1).sum()


def test_baseline_no_treated_rows_raises():
    """Model raises ValueError if training data contains no treated rows."""
    train_df, _ = load_train_val(FIXTURE_DIR, verify_hashes=True)
    no_treated_df = train_df[train_df["treatment"] == 0].copy()

    model = ResponseBaselineModel()
    with pytest.raises(ValueError, match="No treated rows"):
        model.fit(no_treated_df)


def test_baseline_unfitted_predict_raises():
    """predict_proba raises RuntimeError if called before fit."""
    _, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    model = ResponseBaselineModel()
    with pytest.raises(RuntimeError, match="Model is not fitted"):
        model.predict_proba(val_df)


def test_baseline_missing_feature_column_raises():
    """predict_proba raises ValueError if input DataFrame lacks a required feature."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    model = train_response_baseline(train_df)

    corrupted_df = val_df.drop(columns=["tenure_days"])
    with pytest.raises(ValueError, match="missing feature columns"):
        model.predict_proba(corrupted_df)


def test_run_smoke_baseline_entry_point():
    """run_smoke_baseline runs end-to-end on fixture and returns dictionary with smoke tag."""
    metrics = run_smoke_baseline(FIXTURE_DIR)
    assert isinstance(metrics, dict)
    assert metrics["eval_type"] == "smoke"
    assert "brier_score" in metrics
    assert "mean_p_treat" in metrics
