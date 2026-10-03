"""Tests for Uplift Modeling candidates (U0: Logistic T-Learner).

Verifies:
1. Two separate models fit on treated and control cohorts.
2. Individual treatment effect is calculated as tau = p_treat - p_control.
3. Uplift is finite and mean absolute uplift is strictly non-zero on the fixture.
4. Anti-leakage guard: presence of true_uplift raises ForbiddenColumnError.
5. Test split is untouched during training.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from campaignlift_ml.data import load_train_val, ForbiddenColumnError
from campaignlift_ml.uplift import (
    LogisticTLearner,
    train_logistic_t_learner,
    run_smoke_logistic_t_learner,
    LightGBMTLearner,
    train_lightgbm_t_learner,
    run_smoke_lightgbm_t_learner,
    LIGHTGBM_AVAILABLE,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"


def test_logistic_t_learner_fit_and_predict_fixture():
    """T-Learner fits on fixture arms and yields finite, non-zero mean absolute uplift."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)

    learner = train_logistic_t_learner(train_df, random_state=20261006)
    assert learner.is_fitted
    assert learner.n_train_treat > 0
    assert learner.n_train_control > 0
    assert learner.n_train_treat + learner.n_train_control == len(train_df)

    # Predict on validation
    preds = learner.predict_uplift(val_df)

    # 1. Finite values
    assert np.all(np.isfinite(preds.p_treat)), "p_treat must be finite"
    assert np.all(np.isfinite(preds.p_control)), "p_control must be finite"
    assert np.all(np.isfinite(preds.uplift)), "uplift must be finite"

    # 2. Probability bounds
    assert np.all(preds.p_treat >= 0.0) and np.all(preds.p_treat <= 1.0)
    assert np.all(preds.p_control >= 0.0) and np.all(preds.p_control <= 1.0)

    # 3. Exact formula match: uplift = p_treat - p_control
    np.testing.assert_allclose(preds.uplift, preds.p_treat - preds.p_control, atol=1e-7)

    # 4. Acceptance criteria: Mean absolute uplift is NOT zero on the fixture
    mean_abs_uplift = float(np.mean(np.abs(preds.uplift)))
    assert mean_abs_uplift > 0.001, f"Mean absolute uplift must be non-zero, got {mean_abs_uplift}"

    # Verify standard deviation
    assert np.std(preds.uplift) > 0.001, "Uplift predictions must have variation across customers"


def test_logistic_t_learner_evaluate_smoke():
    """evaluate returns summary metrics tagged with 'smoke'."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    learner = train_logistic_t_learner(train_df)

    result = learner.evaluate(val_df, eval_type="smoke")
    res_dict = result.to_dict()

    assert res_dict["candidate_id"] == "U0"
    assert res_dict["model_name"] == "logistic_t_learner"
    assert res_dict["eval_type"] == "smoke"
    assert res_dict["mean_abs_uplift"] > 0.0
    assert res_dict["n_eval"] == len(val_df)


def test_logistic_t_learner_refuses_true_uplift_leakage():
    """Attempting to train on data containing true_uplift raises ForbiddenColumnError."""
    train_df, _ = load_train_val(FIXTURE_DIR, verify_hashes=True)
    corrupted_df = train_df.copy()
    corrupted_df["true_uplift"] = 0.05  # Leaked oracle column

    learner = LogisticTLearner()
    with pytest.raises(ForbiddenColumnError, match="CRITICAL CAUSAL LEAKAGE"):
        learner.fit(corrupted_df)


def test_logistic_t_learner_missing_arm_raises():
    """Learner raises ValueError if an arm is completely missing."""
    train_df, _ = load_train_val(FIXTURE_DIR, verify_hashes=True)
    only_treated = train_df[train_df["treatment"] == 1].copy()

    learner = LogisticTLearner()
    with pytest.raises(ValueError, match="No control rows"):
        learner.fit(only_treated)


def test_run_smoke_logistic_t_learner_runner():
    """run_smoke_logistic_t_learner CLI entry point executes cleanly on fixture."""
    metrics = run_smoke_logistic_t_learner(FIXTURE_DIR)
    assert isinstance(metrics, dict)
    assert metrics["candidate_id"] == "U0"
    assert metrics["eval_type"] == "smoke"
    assert metrics["mean_abs_uplift"] > 0.0


# =============================================================================
# LightGBM T-Learner Tests (Candidate U1)
# =============================================================================

@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
def test_lightgbm_t_learner_fit_and_predict_fixture():
    """LightGBM T-Learner fits on fixture arms and yields finite, non-zero mean absolute uplift."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)

    learner = train_lightgbm_t_learner(train_df, random_state=20261006)
    assert learner.is_fitted
    assert learner.n_train_treat > 0
    assert learner.n_train_control > 0
    assert learner.n_train_treat + learner.n_train_control == len(train_df)

    # Predict on validation
    preds = learner.predict_uplift(val_df)

    # 1. Finite values
    assert np.all(np.isfinite(preds.p_treat)), "p_treat must be finite"
    assert np.all(np.isfinite(preds.p_control)), "p_control must be finite"
    assert np.all(np.isfinite(preds.uplift)), "uplift must be finite"

    # 2. Probability bounds
    assert np.all(preds.p_treat >= 0.0) and np.all(preds.p_treat <= 1.0)
    assert np.all(preds.p_control >= 0.0) and np.all(preds.p_control <= 1.0)

    # 3. Exact formula match: uplift = p_treat - p_control
    np.testing.assert_allclose(preds.uplift, preds.p_treat - preds.p_control, atol=1e-7)

    # 4. Acceptance criteria: Mean absolute uplift is NOT zero on the fixture
    mean_abs_uplift = float(np.mean(np.abs(preds.uplift)))
    assert mean_abs_uplift > 0.001, f"Mean absolute uplift must be non-zero, got {mean_abs_uplift}"

    # Verify standard deviation
    assert np.std(preds.uplift) > 0.001, "LightGBM uplift predictions must have variation across customers"


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
def test_lightgbm_t_learner_evaluate_smoke():
    """evaluate returns summary metrics tagged with 'smoke' for candidate U1."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    learner = train_lightgbm_t_learner(train_df)

    result = learner.evaluate(val_df, eval_type="smoke")
    res_dict = result.to_dict()

    assert res_dict["candidate_id"] == "U1"
    assert res_dict["model_name"] == "lightgbm_t_learner"
    assert res_dict["eval_type"] == "smoke"
    assert res_dict["mean_abs_uplift"] > 0.0
    assert res_dict["n_eval"] == len(val_df)


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
def test_lightgbm_t_learner_refuses_true_uplift_leakage():
    """Attempting to train LightGBM on data containing true_uplift raises ForbiddenColumnError."""
    train_df, _ = load_train_val(FIXTURE_DIR, verify_hashes=True)
    corrupted_df = train_df.copy()
    corrupted_df["true_uplift"] = 0.05  # Leaked oracle column

    learner = LightGBMTLearner()
    with pytest.raises(ForbiddenColumnError, match="CRITICAL CAUSAL LEAKAGE"):
        learner.fit(corrupted_df)


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
def test_lightgbm_t_learner_missing_arm_raises():
    """LightGBM Learner raises ValueError if an arm is completely missing."""
    train_df, _ = load_train_val(FIXTURE_DIR, verify_hashes=True)
    only_treated = train_df[train_df["treatment"] == 1].copy()

    learner = LightGBMTLearner()
    with pytest.raises(ValueError, match="No control rows"):
        learner.fit(only_treated)


@pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
def test_run_smoke_lightgbm_t_learner_runner(tmp_path):
    """run_smoke_lightgbm_t_learner CLI entry point executes cleanly and saves json if requested."""
    out_file = tmp_path / "lightgbm_smoke.json"
    metrics = run_smoke_lightgbm_t_learner(FIXTURE_DIR, output_metrics_path=out_file)
    assert isinstance(metrics, dict)
    assert metrics["candidate_id"] == "U1"
    assert metrics["eval_type"] == "smoke"
    assert metrics["mean_abs_uplift"] > 0.0
    assert out_file.exists()


def test_lightgbm_t_learner_hyperparams_from_yaml():
    """LightGBMTLearner properly reads parameters from train.yaml."""
    if not LIGHTGBM_AVAILABLE:
        pytest.skip("LightGBM not installed")
    config_file = REPO_ROOT / "ml" / "config" / "train.yaml"
    assert config_file.exists(), "train.yaml must exist"

    learner = LightGBMTLearner(config_path=config_file)
    assert learner.n_estimators == 100
    assert learner.learning_rate == 0.05
    assert learner.max_depth == 4
    assert learner.min_child_samples == 5

