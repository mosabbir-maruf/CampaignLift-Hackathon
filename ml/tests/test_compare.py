"""Unit tests for Strategy Comparison Calculator (Step 15.2).

Verifies:
1. Budget is strictly respected across Random, Response, and Uplift strategies.
2. Acceptance criteria: Response and Uplift selections are not identical on the fixture.
3. Selections identical flag and reason are properly set when budget selects entire cohort.
4. Uplift strategy excludes negative uplift customers when configured.
5. Strict separation and labeling of 'expected_from_scores' vs 'measured'.
6. Undefined cost ratio note when measured incremental transactions are <= 0.
7. Reproducibility of random selection with documented seed.
"""

import numpy as np
import pandas as pd
import pytest

from campaignlift_ml.compare import (
    DEFAULT_BUDGET_BDT,
    DEFAULT_COST_PER_CUSTOMER_BDT,
    DEFAULT_RANDOM_SEED,
    compare_strategies,
    run_smoke_strategy_comparison,
)
from campaignlift_ml.data import load_train_val
from campaignlift_ml.uplift import train_logistic_t_learner


@pytest.fixture
def scored_fixture_val():
    """Produce validation split scored by LogisticTLearner."""
    train_df, val_df = load_train_val("data/fixtures/fixture_v1", verify_hashes=True)
    learner = train_logistic_t_learner(train_df)
    preds = learner.predict_uplift(val_df)

    scored = val_df.copy()
    scored["p_treat"] = preds.p_treat
    scored["p_control"] = preds.p_control
    scored["uplift"] = preds.uplift
    return scored


def test_strategy_comparison_budget_respected(scored_fixture_val):
    """Budget must be respected by all three strategies."""
    budget = 100.0
    cost = 10.0
    res = compare_strategies(
        eval_df=scored_fixture_val,
        budget_bdt=budget,
        cost_per_customer_bdt=cost,
    )

    for strat in [res.random, res.response, res.uplift]:
        assert strat.budget_respected, f"{strat.strategy_name} exceeded budget"
        assert strat.total_spend_bdt <= budget
        assert strat.selected_count <= int(budget // cost)


def test_response_and_uplift_selections_not_identical_on_fixture(scored_fixture_val):
    """Acceptance criteria: Response and uplift selections are not identical on the fixture."""
    res = compare_strategies(
        eval_df=scored_fixture_val,
        budget_bdt=100.0,
        cost_per_customer_bdt=10.0,
    )

    assert not res.selections_identical, (
        "Response and uplift selections should not be identical on the fixture when scores differ"
    )
    assert res.identical_reason is None

    # Verify set difference
    response_ids = set(res.response.selected_customer_ids)
    uplift_ids = set(res.uplift.selected_customer_ids)
    assert response_ids != uplift_ids


def test_identical_selections_recorded_when_budget_accommodates_all(scored_fixture_val):
    """When budget is large enough to select all available customers, selections_identical is recorded."""
    # Huge budget covers all 23 customers
    huge_budget = 5000.0
    cost = 10.0
    res = compare_strategies(
        eval_df=scored_fixture_val,
        budget_bdt=huge_budget,
        cost_per_customer_bdt=cost,
        exclude_negative_uplift=False,  # allow all
    )

    assert res.selections_identical
    assert "entire audience" in res.identical_reason


def test_uplift_excludes_negative_uplift(scored_fixture_val):
    """Uplift strategy must exclude negative uplift customers when exclude_negative_uplift=True."""
    res = compare_strategies(
        eval_df=scored_fixture_val,
        budget_bdt=100.0,
        cost_per_customer_bdt=10.0,
        exclude_negative_uplift=True,
    )

    uplift_eval = res.uplift
    assert uplift_eval.expected_from_scores["negative_uplift_share"] == 0.0

    # Meanwhile response model does not exclude them
    response_eval = res.response
    assert response_eval.expected_from_scores["negative_uplift_share"] > 0.0


def test_expected_vs_measured_block_separation(scored_fixture_val):
    """Check that expected_from_scores and measured blocks are distinct and populated."""
    res = compare_strategies(
        eval_df=scored_fixture_val,
        budget_bdt=100.0,
        cost_per_customer_bdt=10.0,
    )

    for strat in [res.random, res.response, res.uplift]:
        exp = strat.expected_from_scores
        meas = strat.measured

        # Expected block contains model predictions
        assert "mean_predicted_response" in exp
        assert "mean_predicted_uplift" in exp
        assert "expected_incremental_transactions" in exp
        assert "negative_uplift_share" in exp

        # Measured block contains factual counts and outcomes
        assert "n_selected" in meas
        assert "n_treated" in meas
        assert "n_control" in meas
        assert "factual_treated_rate" in meas
        assert "factual_control_rate" in meas
        assert "measured_incremental_rate" in meas
        assert "has_sufficient_support" in meas


def test_undefined_cost_ratio_when_incremental_txns_nonpositive():
    """Cost ratio is undefined if measured incremental transactions are <= 0."""
    # Synthetic frame where treatment outcome <= control outcome
    eval_df = pd.DataFrame(
        {
            "customer_id": [f"C{i:03d}" for i in range(10)],
            "p_treat": [0.9 - 0.05 * i for i in range(10)],
            "uplift": [0.5 - 0.05 * i for i in range(10)],
            "y_transacted": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],  # treated has 0 responders, control has 1
            "treatment": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
        }
    )

    res = compare_strategies(eval_df, budget_bdt=50.0, cost_per_customer_bdt=10.0)

    for strat in [res.random, res.response, res.uplift]:
        meas = strat.measured
        # If treated rate <= control rate, measured_cost_per_incremental_txn_bdt must be None
        if meas.get("measured_incremental_transactions") is not None and meas["measured_incremental_transactions"] <= 0:
            assert meas["measured_cost_per_incremental_txn_bdt"] is None
            assert "undefined" in meas["measured_cost_ratio_note"]


def test_random_seed_reproducibility(scored_fixture_val):
    """Random strategy is strictly reproducible with the documented seed."""
    res1 = compare_strategies(scored_fixture_val, budget_bdt=100.0, random_seed=20261006)
    res2 = compare_strategies(scored_fixture_val, budget_bdt=100.0, random_seed=20261006)
    res_diff = compare_strategies(scored_fixture_val, budget_bdt=100.0, random_seed=999999)

    assert res1.random.selected_indices == res2.random.selected_indices
    assert res1.random.selected_indices != res_diff.random.selected_indices


def test_run_smoke_strategy_comparison_runner():
    """run_smoke_strategy_comparison entry point runs cleanly and returns serializable dict."""
    res_dict = run_smoke_strategy_comparison()
    assert isinstance(res_dict, dict)
    assert res_dict["budget_bdt"] == 100.0
    assert "strategies" in res_dict
    assert "random" in res_dict["strategies"]
    assert "response" in res_dict["strategies"]
    assert "uplift" in res_dict["strategies"]
    assert not res_dict["selections_identical"]
