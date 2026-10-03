"""Unit tests for Uplift Metrics (Step 15.1: Qini, Cumulative Gain, Support Checks).

Verifies:
1. Hand-computed analytical validation on a known tiny frame matches hand-calculated numbers.
2. Inverted ranking produces negative Qini score.
3. Randomized support constraint: slices with <30 treated or <30 control return insufficient support.
4. Cumulative gain curve endpoint equals the sample Average Treatment Effect (ATE).
5. Treatment rate calculation inside selected audiences.
6. Execution on real fixture validation split produces valid, non-trivial Qini metrics without reading test.
"""

import numpy as np
import pandas as pd
import pytest

from campaignlift_ml.data import load_train_val
from campaignlift_ml.metrics import (
    compute_cumulative_gain_curve,
    compute_incremental_response,
    compute_qini_curve,
    compute_qini_score,
    compute_top_decile_incremental_response,
    compute_treatment_rate,
    evaluate_uplift_predictions,
)
from campaignlift_ml.uplift import train_logistic_t_learner


def test_hand_computed_tiny_frame_qini():
    """Unit test on a hand-built tiny frame with known arm counts returns the exact hand-computed value.

    Hand-calculated setup:
    N = 6 customers
    order sorted by preds descending:
      idx  pred   t  y   y_t_cum  y_c_cum  Q(k) = y_t - y_c*(3/3)
      0    0.80   1  1      1        0      1.0
      1    0.60   0  0      1        0      1.0
      2    0.40   1  1      2        0      2.0
      3    0.20   0  1      2        1      1.0
      4   -0.10   1  0      2        1      1.0
      5   -0.30   0  0      2        1      1.0

    Expected Qini curve: [0.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0]
    Normalized pop fraction: [0, 1/6, 2/6, 3/6, 4/6, 5/6, 1.0]
    Area(Q) via trapezoid = (1/6) * (0.5 + 1.0 + 1.5 + 1.5 + 1.0 + 1.0) = 6.5 / 6
    Area(Random) = 0.5 * 1.0 = 3.0 / 6
    Qini score = (6.5 - 3.0) / 6 = 3.5 / 6 = 0.5833333333333334
    """
    y_true = np.array([1, 0, 1, 1, 0, 0])
    treatment = np.array([1, 0, 1, 0, 1, 0])
    uplift_preds = np.array([0.8, 0.6, 0.4, 0.2, -0.1, -0.3])

    res = compute_qini_curve(y_true, uplift_preds, treatment)

    assert res.n_samples == 6
    assert res.n_treated == 3
    assert res.n_control == 3

    # Exact Qini curve matching hand calculations
    expected_qini_curve = np.array([0.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0])
    np.testing.assert_allclose(res.qini_curve, expected_qini_curve, atol=1e-10)

    # Exact Area and Qini score check
    expected_qini_score = 3.5 / 6.0
    assert pytest.approx(expected_qini_score, rel=1e-6) == res.qini_score

    # Check convenience function matches
    score = compute_qini_score(y_true, uplift_preds, treatment)
    assert pytest.approx(expected_qini_score, rel=1e-6) == score


def test_inverted_ranking_produces_negative_qini():
    """Reversing the predicted ranking inverts the curve below the random line."""
    y_true = np.array([1, 0, 1, 1, 0, 0])
    treatment = np.array([1, 0, 1, 0, 1, 0])
    # Inverted predictions
    inverted_preds = np.array([-0.8, -0.6, -0.4, -0.2, 0.1, 0.3])

    res = compute_qini_curve(y_true, inverted_preds, treatment)
    assert res.qini_score < 0.0, "Inverted predictions should yield negative Qini score"


def test_cumulative_gain_curve_endpoint_equals_ate():
    """Cumulative gain curve endpoint must match the factual Average Treatment Effect (ATE)."""
    y_true = np.array([1, 0, 1, 1, 0, 0])
    treatment = np.array([1, 0, 1, 0, 1, 0])
    uplift_preds = np.array([0.8, 0.6, 0.4, 0.2, -0.1, -0.3])

    res = compute_cumulative_gain_curve(y_true, uplift_preds, treatment)

    # Y_t/N_t = 2/3, Y_c/N_c = 1/3 => ATE = 1/3
    expected_ate = 2.0 / 3.0 - 1.0 / 3.0
    assert pytest.approx(expected_ate, rel=1e-6) == res.ate
    assert pytest.approx(expected_ate, rel=1e-6) == res.gain_curve[-1]


def test_insufficient_randomized_support_rule():
    """Rule: Return insufficient support when slice has <30 treated or <30 control."""
    # Case 1: 29 treated, 50 control (treated < 30)
    y_small_t = np.ones(79)
    t_small_t = np.array([1] * 29 + [0] * 50)
    res_small_t = compute_incremental_response(y_small_t, t_small_t, min_support=30)
    assert not res_small_t.has_sufficient_support
    assert res_small_t.status == "insufficient_randomized_support"
    assert res_small_t.incremental_rate is None
    assert "insufficient randomized support" in res_small_t.message

    # Case 2: 50 treated, 25 control (control < 30)
    y_small_c = np.ones(75)
    t_small_c = np.array([1] * 50 + [0] * 25)
    res_small_c = compute_incremental_response(y_small_c, t_small_c, min_support=30)
    assert not res_small_c.has_sufficient_support
    assert res_small_c.status == "insufficient_randomized_support"
    assert res_small_c.incremental_rate is None

    # Case 3: 35 treated (14 responders), 35 control (7 responders) => Valid!
    y_ok = np.array([1] * 14 + [0] * 21 + [1] * 7 + [0] * 28)
    t_ok = np.array([1] * 35 + [0] * 35)
    res_ok = compute_incremental_response(y_ok, t_ok, min_support=30)
    assert res_ok.has_sufficient_support
    assert res_ok.status == "ok"
    assert res_ok.treated_rate == pytest.approx(14 / 35, rel=1e-6)
    assert res_ok.control_rate == pytest.approx(7 / 35, rel=1e-6)
    assert res_ok.incremental_rate == pytest.approx((14 / 35) - (7 / 35), rel=1e-6)


def test_treatment_rate_calculation():
    """Compute treatment rate inside audience correctly."""
    treatment = np.array([1, 1, 0, 1, 0, 0, 1, 0])
    rate = compute_treatment_rate(treatment)
    assert rate == 0.5

    assert compute_treatment_rate(np.array([])) == 0.0


def test_evaluate_uplift_predictions_on_fixture():
    """Verify evaluation metrics on real fixture validation split without touching test."""
    train_df, val_df = load_train_val("data/fixtures/fixture_v1", verify_hashes=True)

    # Train model on train split
    model = train_logistic_t_learner(train_df)
    preds = model.predict_uplift(val_df)

    # Evaluate on validation split
    metrics = evaluate_uplift_predictions(
        y_true=val_df["y_transacted"],
        uplift_preds=preds.uplift,
        treatment=val_df["treatment"],
        candidate_id="U0",
        model_name="logistic_t_learner",
    )

    assert metrics["candidate_id"] == "U0"
    assert metrics["model_name"] == "logistic_t_learner"
    assert metrics["n_eval"] == len(val_df)
    assert metrics["n_treated"] > 0
    assert metrics["n_control"] > 0
    assert 0.0 <= metrics["treatment_rate"] <= 1.0
    assert np.isfinite(metrics["qini_score"])
    assert np.isfinite(metrics["ate"])


def test_input_validation_errors():
    """Invalid input shapes or treatment values raise appropriate ValueErrors."""
    with pytest.raises(ValueError, match="Input length mismatch"):
        compute_qini_curve(np.array([1, 0]), np.array([0.5]), np.array([1, 0]))

    with pytest.raises(ValueError, match="must not be empty"):
        compute_qini_curve(np.array([]), np.array([]), np.array([]))

    with pytest.raises(ValueError, match="Treatment must be binary"):
        compute_qini_curve(np.array([1, 0]), np.array([0.5, 0.2]), np.array([1, 2]))
