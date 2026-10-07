"""Unit tests for Seed and Assignment Sensitivity module.

Verifies:
1. Stability of 5-seed evaluation on validation split without mutating champion.
2. Treatment assignment distribution shift generation (target p=0.30).
3. Baseline ladder comparison across 3 models: response propensity, logistic T-learner, LightGBM S-learner.
4. Result JSON serialization and invariant assertions.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from campaignlift_ml.data import TARGET_COLUMN, TREATMENT_COLUMN, load_train_val
from campaignlift_ml.sensitivity import (
    DEFAULT_SEEDS,
    DEFAULT_SHIFTED_TREATMENT_RATE,
    create_shifted_validation_cohort,
    run_assignment_sensitivity_comparison,
    run_repeated_seeds_evaluation,
    run_sensitivity_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "models" / "cl-model-ml_dev_20261006-lgbm_s_learner-r01"


def test_default_constants():
    """Verify default seeds and target shifted treatment rate."""
    assert len(DEFAULT_SEEDS) == 5
    assert DEFAULT_SEEDS == [20261006, 20261007, 20261008, 20261009, 20261010]
    assert DEFAULT_SHIFTED_TREATMENT_RATE == 0.30


def test_create_shifted_validation_cohort():
    """Verify treatment assignment probability shift creates valid cohort with p approx 0.3."""
    # Synthetic cohort with 70 controls and 70 treated (p = 0.50)
    df = pd.DataFrame({
        "customer_id": [f"C_{i}" for i in range(140)],
        TREATMENT_COLUMN: [0] * 70 + [1] * 70,
        TARGET_COLUMN: [0, 1] * 70,
        "days_since_last_txn": [10] * 140,
    })

    shifted = create_shifted_validation_cohort(df, target_treatment_rate=0.30, seed=42)

    # All controls must be retained
    assert (shifted[TREATMENT_COLUMN] == 0).sum() == 70
    n_treated = (shifted[TREATMENT_COLUMN] == 1).sum()
    total = len(shifted)
    observed_p = n_treated / total

    # Desired treated: 70 * 0.30 / 0.70 = 30; total = 100; p = 0.30
    assert n_treated == 30
    assert total == 100
    assert pytest.approx(observed_p, abs=0.01) == 0.30


def test_create_shifted_validation_cohort_empty_arms_raises():
    """Verify error handling when a treatment arm is missing."""
    df_no_treat = pd.DataFrame({
        TREATMENT_COLUMN: [0, 0, 0],
        TARGET_COLUMN: [0, 1, 0],
    })
    with pytest.raises(ValueError, match="Validation DataFrame must contain both treatment arms"):
        create_shifted_validation_cohort(df_no_treat)


def test_run_repeated_seeds_evaluation_on_fixture():
    """Verify repeated-seeds evaluation runs across specified seeds."""
    train_df, val_df = load_train_val(FIXTURE_DIR)
    test_seeds = [20261006, 20261007]

    res = run_repeated_seeds_evaluation(train_df, val_df, seeds=test_seeds)

    summary = res["summary"]
    assert summary["seeds_requested"] == 2
    assert summary["seeds_completed"] == 2
    assert summary["min_auuc"] <= summary["mean_auuc"] <= summary["max_auuc"]
    assert summary["auuc_spread"] >= 0.0

    seed_results = res["seed_results"]
    assert len(seed_results) == 2
    for item in seed_results:
        assert item["status"] == "completed"
        assert item["validation_auuc"] is not None
        assert item["validation_qini"] is not None


def test_run_assignment_sensitivity_comparison():
    """Verify baseline ladder comparison under baseline and shifted assignment."""
    train_df, val_df = load_train_val(FIXTURE_DIR)
    shifted_val_df = create_shifted_validation_cohort(val_df, target_treatment_rate=0.30)

    rows = run_assignment_sensitivity_comparison(
        train_df=train_df,
        val_df=val_df,
        shifted_val_df=shifted_val_df,
        artifact_dir=ARTIFACT_DIR,
    )

    # 2 conditions x 3 models = 6 rows
    assert len(rows) == 6

    models = {r["model"] for r in rows}
    assert models == {"response_propensity", "logistic_t_learner", "lightgbm_s_learner"}

    conditions = {r["condition"] for r in rows}
    assert "baseline_rct (p=0.5)" in conditions
    assert "shifted_assignment (p=0.3)" in conditions

    for r in rows:
        assert "condition" in r
        assert "model" in r
        assert "AUUC" in r
        assert "top_decile_incremental_rate" in r
        assert "n" in r
        assert isinstance(r["AUUC"], float)
        assert isinstance(r["top_decile_incremental_rate"], float)
        assert r["n"] > 0


def test_run_sensitivity_pipeline_e2e(tmp_path):
    """Verify full sensitivity pipeline execution and JSON writing."""
    out_file = tmp_path / "sensitivity_test.json"

    report = run_sensitivity_pipeline(
        dataset_dir=FIXTURE_DIR,
        artifact_dir=ARTIFACT_DIR,
        seeds=[20261006, 20261007],
        target_treatment_rate=0.30,
        output_path=out_file,
    )

    assert out_file.exists()
    with out_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["frozen_model"] == "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
    assert data["champion_status"] == "unchanged"
    assert "repeated_seeds" in data
    assert data["repeated_seeds"]["summary"]["seeds_completed"] == 2
    assert "assignment_sensitivity" in data
    assert len(data["assignment_sensitivity"]["comparison_table"]) == 6
