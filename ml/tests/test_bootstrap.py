"""Unit tests for Bootstrap Confidence Intervals module.

Verifies:
1. Unit test of interval math on fixed tiny array: lower <= point_estimate <= upper.
2. Precommitted settings: 200 resamples, seed 20261006, percentiles (2.5, 97.5).
3. End-to-end bootstrap execution with model artifact and JSON serialization.
4. No refitting contract.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from campaignlift_ml.bootstrap import (
    PRECOMMITTED_PERCENTILES,
    PRECOMMITTED_RESAMPLES,
    PRECOMMITTED_SEED,
    bootstrap_arrays,
    compute_percentile_interval,
    run_bootstrap_evaluation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "models" / "cl-model-ml_dev_20261006-lgbm_s_learner-r01"


def test_compute_percentile_interval():
    """Verify percentile calculation on known distribution."""
    dist = np.linspace(0, 100, 1001)
    lower, upper = compute_percentile_interval(dist, 2.5, 97.5)
    assert lower == pytest.approx(2.5, abs=0.1)
    assert upper == pytest.approx(97.5, abs=0.1)
    assert lower < upper

    with pytest.raises(ValueError, match="empty distribution"):
        compute_percentile_interval([])


def test_bootstrap_math_on_fixed_tiny_array():
    """Requirement 7: Unit-test interval math on a tiny fixed array:
    lower bound <= point estimate <= upper bound for a known seed.
    """
    # Deterministic fixed tiny cohort
    y = np.array([1, 0, 1, 0, 1, 0, 0, 1, 1, 0])
    preds = np.array([0.5, -0.2, 0.4, -0.1, 0.3, -0.3, 0.0, 0.2, 0.35, -0.15])
    t = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0])

    res = bootstrap_arrays(
        y_true=y,
        uplift_preds=preds,
        treatment=t,
        n_resamples=100,
        seed=PRECOMMITTED_SEED,
        lower_pct=2.5,
        upper_pct=97.5,
    )

    qini = res["qini"]
    auuc = res["auuc"]

    # Point estimates must be within the empirical bounds
    assert qini.ci_lower <= qini.point_estimate <= qini.ci_upper, (
        f"Qini point {qini.point_estimate} not in [{qini.ci_lower}, {qini.ci_upper}]"
    )
    assert auuc.ci_lower <= auuc.point_estimate <= auuc.ci_upper, (
        f"AUUC point {auuc.point_estimate} not in [{auuc.ci_lower}, {auuc.ci_upper}]"
    )
    assert qini.resamples_completed > 0
    assert auuc.resamples_completed > 0
    assert qini.seed == PRECOMMITTED_SEED


def test_precommitted_constants():
    """Verify pre-committed configuration matches instructions."""
    assert PRECOMMITTED_RESAMPLES == 200
    assert PRECOMMITTED_SEED == 20261006
    assert PRECOMMITTED_PERCENTILES == (2.5, 97.5)


def test_run_bootstrap_evaluation_saves_json(tmp_path):
    """Verify end-to-end execution on fixture test split and JSON serialization."""
    out_file = tmp_path / "bootstrap_test.json"

    report = run_bootstrap_evaluation(
        artifact_dir=ARTIFACT_DIR,
        dataset_dir=FIXTURE_DIR,
        n_resamples=50,
        seed=PRECOMMITTED_SEED,
        output_path=out_file,
    )

    assert out_file.exists()
    with out_file.open("r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["candidate_id"] == "U2"
    assert loaded["model_version"] == "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
    assert "metrics" in loaded
    assert "qini" in loaded["metrics"]
    assert "auuc" in loaded["metrics"]
    assert loaded["precommitted_settings"]["refit_performed"] is False
    assert loaded["metrics"]["qini"]["resamples_completed"] > 0
