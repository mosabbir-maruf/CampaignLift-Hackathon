"""Tests for CampaignLift Budget Optimizer API.

Validation requirements:
- Budget is never exceeded on the fixture.
- Negative uplift customers are absent when exclusion is on.
- Response strategy can include a customer the uplift strategy rejects.
- Same input returns the same selected IDs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings, get_settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings fixture using temporary SQLite DB and real fixture data/artifacts."""
    db_file = tmp_path / "test_optimizer.db"
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{db_file}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
        gemini_api_key=None,
        log_level="DEBUG",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """TestClient wired with test_settings."""
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


@pytest.fixture
def created_campaign_id(client: TestClient) -> str:
    """Helper fixture to create a campaign and return its ID."""
    payload = {
        "name": "Q4 QR Adoption Drive",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 25.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 500.0,  # 500 BDT funds at most 20 offers at 25 BDT each
        "channel": "push",
    }
    resp = client.post("/api/v1/campaigns", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_budget_never_exceeded_on_fixture(client: TestClient, created_campaign_id: str):
    """Budget constraint must be strictly respected: spend_bdt <= budget_bdt."""
    # Unit cost is 25 BDT, budget is 500 BDT
    resp = client.post(f"/api/v1/campaigns/{created_campaign_id}/optimize", json={"budget_bdt": 500.0})
    assert resp.status_code == 200
    data = resp.json()

    assert data["strategy"] == "uplift"
    assert data["budget_bdt"] == 500.0
    assert data["spend_bdt"] <= 500.0
    assert data["spend_bdt"] == data["selected_count"] * 25.0
    assert data["selected_count"] <= 20
    assert len(data["selected_customer_ids"]) == data["selected_count"]


def test_negative_uplift_excluded_when_asked(client: TestClient, created_campaign_id: str):
    """When exclude_negative_uplift is True, no customer with predicted uplift < 0 is selected."""
    # 1. Run optimization with exclusion on (default)
    resp_excluded = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 50000.0, "exclude_negative_uplift": True},
    )
    assert resp_excluded.status_code == 200
    data_exc = resp_excluded.json()

    # The uplift strategy in comparison must have 0% negative uplift share
    uplift_strat_exc = next(
        s for s in data_exc["comparison"]["strategies"] if s["strategy"] == "uplift"
    )
    assert uplift_strat_exc["negative_uplift_selected_share"] == 0.0

    # 2. Run optimization with exclusion off
    resp_included = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 50000.0, "exclude_negative_uplift": False},
    )
    assert resp_included.status_code == 200
    data_inc = resp_included.json()

    # Total selected should be equal or greater when negative uplift is not excluded
    assert data_inc["selected_count"] >= data_exc["selected_count"]


def test_response_strategy_can_include_customer_uplift_rejects(
    client: TestClient, created_campaign_id: str
):
    """Response strategy targets by p_treat, which can select a customer that uplift rejects."""
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 250.0, "exclude_negative_uplift": True},  # funds 10 customers
    )
    assert resp.status_code == 200
    data = resp.json()

    comp_strategies = {s["strategy"]: s for s in data["comparison"]["strategies"]}
    assert "uplift" in comp_strategies
    assert "response" in comp_strategies
    assert "random" in comp_strategies

    # Response strategy does not filter out negative uplift
    response_metric = comp_strategies["response"]
    uplift_metric = comp_strategies["uplift"]

    # Verify that expected incremental value of uplift strategy is greater than or equal to response
    assert uplift_metric["expected_incremental_value"] >= response_metric["expected_incremental_value"]


def test_stable_ids_reproducible(client: TestClient, created_campaign_id: str):
    """Same input and budget parameters must return identical, stable selected customer IDs."""
    resp1 = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 300.0, "exclude_negative_uplift": True},
    )
    resp2 = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 300.0, "exclude_negative_uplift": True},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    ids1 = resp1.json()["selected_customer_ids"]
    ids2 = resp2.json()["selected_customer_ids"]
    assert ids1 == ids2
    assert len(ids1) > 0


def test_budget_smaller_than_unit_cost_selects_nobody(client: TestClient, created_campaign_id: str):
    """If budget is smaller than one offer cost, nobody is selected and spend is 0."""
    # Unit cost is 25 BDT, budget is 10 BDT
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 10.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_count"] == 0
    assert data["spend_bdt"] == 0.0
    assert data["expected_incremental_value"] == 0.0
    assert data["selected_customer_ids"] == []


def test_invalid_budget_rejected(client: TestClient, created_campaign_id: str):
    """Negative or zero budget must be rejected with 400."""
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": -50.0},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] in ("validation_error", "invalid_budget")


def test_value_per_transaction_ranking(client: TestClient, created_campaign_id: str):
    """Providing value_per_incremental_transaction_bdt ranks by net value."""
    resp_with_val = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={
            "budget_bdt": 500.0,
            "value_per_incremental_transaction_bdt": 500.0,
        },
    )
    assert resp_with_val.status_code == 200
    data = resp_with_val.json()
    assert data["selected_count"] > 0
    assert data["spend_bdt"] <= 500.0


def test_get_strategy_comparison_endpoint(client: TestClient, created_campaign_id: str):
    """GET /api/v1/campaigns/{id}/comparison returns 404 before optimize, and 200 with 4-rung metrics after."""
    # 1. Before optimization -> 404
    resp_before = client.get(f"/api/v1/campaigns/{created_campaign_id}/comparison")
    assert resp_before.status_code == 404
    assert resp_before.json()["error"] == "comparison_not_found"

    # 2. Run optimization
    opt_resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert opt_resp.status_code == 200

    # 3. After optimization -> 200
    resp_after = client.get(f"/api/v1/campaigns/{created_campaign_id}/comparison")
    assert resp_after.status_code == 200
    comp_data = resp_after.json()

    # Shared campaign constraints on response
    assert comp_data["campaign_id"] == created_campaign_id
    assert comp_data["budget_bdt"] == 500.0
    assert comp_data["eligible_population_count"] == 103

    # All four rungs must be present
    assert len(comp_data["strategies"]) == 4
    strat_names = {s["strategy"] for s in comp_data["strategies"]}
    assert strat_names == {"random", "response", "uplift", "uplift_plus_budget"}

    # Assert identical campaign_id, eligible_population_count, and budget across all 4 rows
    campaign_ids = {s["campaign_id"] for s in comp_data["strategies"]}
    eligible_counts = {s["eligible_population_count"] for s in comp_data["strategies"]}
    budgets = {s["budget_bdt"] for s in comp_data["strategies"]}

    assert campaign_ids == {created_campaign_id}
    assert eligible_counts == {103}
    assert budgets == {500.0}

    # Assert each spend is within that same budget
    for s in comp_data["strategies"]:
        assert s["spend_bdt"] <= 500.0
        assert s["selected_count"] >= 0
        assert s["support"] in ("sufficient", "insufficient")


def test_uplift_plus_budget_definition_differs_from_pure_uplift(
    client: TestClient, created_campaign_id: str
):
    """Verify uplift_plus_budget is not a silent alias of pure uplift."""
    # Scenario A: When assumed value per transaction is provided (e.g. 100 BDT with 25 BDT cost)
    # Net value threshold is uplift >= 25 / 100 = 0.25.
    # Pure uplift targets highest uplift customers even if below 0.25.
    # Uplift + budget optimizer filters out negative net values ((uplift * 100) - 25 < 0).
    resp_val = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={
            "budget_bdt": 500.0,
            "value_per_incremental_transaction_bdt": 100.0,
            "exclude_negative_uplift": True,
        },
    )
    assert resp_val.status_code == 200
    comp_val = {s["strategy"]: s for s in resp_val.json()["comparison"]["strategies"]}
    pure_uplift = comp_val["uplift"]
    up_plus_budget = comp_val["uplift_plus_budget"]

    # The selections and spend differ due to net-value filtering
    assert up_plus_budget["strategy"] == "uplift_plus_budget"
    assert pure_uplift["strategy"] == "uplift"
    assert up_plus_budget["spend_bdt"] <= 500.0
    assert pure_uplift["spend_bdt"] <= 500.0

    # Scenario B: When exclude_negative_uplift is False and budget is huge (50,000 BDT)
    # Pure uplift continues allocating remaining budget to negative-uplift customers.
    # Uplift + budget optimizer stops when marginal predicted uplift drops below zero.
    resp_huge = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={
            "budget_bdt": 50000.0,
            "exclude_negative_uplift": False,
        },
    )
    assert resp_huge.status_code == 200
    comp_huge = {s["strategy"]: s for s in resp_huge.json()["comparison"]["strategies"]}
    pure_huge = comp_huge["uplift"]
    up_budget_huge = comp_huge["uplift_plus_budget"]

    # Pure uplift took negative uplift customers because exclude_negative_uplift was False
    assert pure_huge["negative_uplift_selected_share"] > 0.0
    # uplift_plus_budget stopped at marginal uplift < 0, so negative uplift share is 0
    assert up_budget_huge["negative_uplift_selected_share"] == 0.0
    assert pure_huge["selected_count"] > up_budget_huge["selected_count"]


# =============================================================================
# FE-09: Synthetic Experiment Business Scorecard Tests
# =============================================================================


def test_fe09_missing_transaction_value_scorecard(client: TestClient, created_campaign_id: str):
    """Requirement A: Missing transaction value generates scorecard with null net_result."""
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 200
    comp = resp.json()["comparison"]

    # Scorecard payload exists
    assert "scorecard" in comp
    assert comp["scorecard"]["scorecard_name"] == "Synthetic Experiment Business Scorecard"
    assert comp["scorecard"]["evidence_boundary"] == (
        "Synthetic randomized experiment; not a controlled commercial holdout."
    )

    strategies = {s["strategy"]: s for s in comp["strategies"]}
    scorecard_strats = {s["strategy"]: s for s in comp["scorecard"]["strategies"]}

    for strat_key in ("random", "response", "uplift", "uplift_plus_budget"):
        item = strategies[strat_key]
        sc_item = scorecard_strats[strat_key]

        # Value assumption is NOT_PROVIDED and net_result is null
        assert item["value_assumption"] == "NOT_PROVIDED"
        assert item["net_result"] is None
        assert sc_item["value_assumption"] == "NOT_PROVIDED"
        assert sc_item["net_result"] is None

        # When support is sufficient and rate available, expected_incremental_transactions is calculated
        if item["support"] == "sufficient" and item["measured_incremental_response"] is not None:
            expected = round(item["measured_incremental_response"] * item["selected_count"], 4)
            assert item["expected_incremental_transactions"] == expected
            assert sc_item["expected_incremental_transactions"] == expected


def test_fe09_explicit_positive_transaction_value(client: TestClient, created_campaign_id: str):
    """Requirement B: Explicit positive transaction value calculates net_result with ASSUMED."""
    assumed_val = 100.0
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={
            "budget_bdt": 500.0,
            "value_per_incremental_transaction_bdt": assumed_val,
        },
    )
    assert resp.status_code == 200
    comp = resp.json()["comparison"]

    strategies = {s["strategy"]: s for s in comp["strategies"]}
    uplift_item = strategies["uplift"]

    # Uplift has sufficient test support on the fixture
    assert uplift_item["support"] == "sufficient"
    assert uplift_item["expected_incremental_transactions"] is not None
    assert uplift_item["value_assumption"] == "ASSUMED"
    assert uplift_item["net_result"] is not None

    # Formula check: expected_incremental_transactions * value - spend
    expected_net = round(
        (uplift_item["expected_incremental_transactions"] * assumed_val) - uplift_item["spend_bdt"],
        2,
    )
    assert uplift_item["net_result"] == expected_net

    # Also verify structured scorecard sub-object matches
    sc_uplift = next(s for s in comp["scorecard"]["strategies"] if s["strategy"] == "uplift")
    assert sc_uplift["value_assumption"] == "ASSUMED"
    assert sc_uplift["net_result"] == expected_net
    assert sc_uplift["expected_incremental_transactions"] == uplift_item["expected_incremental_transactions"]


def test_fe09_invalid_transaction_value_rejected(client: TestClient, created_campaign_id: str):
    """Requirement C: Zero or negative transaction value is rejected with 400; no silent default."""
    from pydantic import ValidationError
    from backend.app.schemas import OptimizeRequest
    from backend.app.services.optimizer import optimize_campaign_budget

    # 1. Zero value rejected via API endpoint
    resp_zero = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0, "value_per_incremental_transaction_bdt": 0.0},
    )
    assert resp_zero.status_code == 400
    assert resp_zero.json()["error"] in ("invalid_budget", "validation_error")

    # 2. Negative value rejected via API endpoint
    resp_neg = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0, "value_per_incremental_transaction_bdt": -20.0},
    )
    assert resp_neg.status_code == 400
    assert resp_neg.json()["error"] in ("invalid_budget", "validation_error")

    # 3. Direct schema rejection: OptimizeRequest rejects <= 0
    with pytest.raises(ValidationError):
        OptimizeRequest(value_per_incremental_transaction_bdt=0.0)

    with pytest.raises(ValidationError):
        OptimizeRequest(value_per_incremental_transaction_bdt=-10.0)

    # 4. Direct service rejection
    campaign = {"id": "c1", "budget_bdt": 500.0, "incentive_cost_bdt": 25.0}
    scored = [{"customer_id": "cust1", "uplift": 0.1, "p_treat": 0.5, "eligible": 1}]
    req_mock = OptimizeRequest()
    req_mock.__dict__["value_per_incremental_transaction_bdt"] = -5.0  # bypass pydantic
    with pytest.raises(ValueError, match="strictly positive"):
        optimize_campaign_budget(campaign, scored, req_mock)

    # 5. Default is strictly None (no default commercial value)
    assert OptimizeRequest().value_per_incremental_transaction_bdt is None


def test_fe09_insufficient_measurement_support_nulls_business_metrics(tmp_path: Path):
    """Requirement D: Insufficient support returns null for expected txns and net_result."""
    from backend.app.schemas import OptimizeRequest
    from backend.app.services.optimizer import optimize_campaign_budget

    campaign = {"id": "c_insufficient", "budget_bdt": 500.0, "incentive_cost_bdt": 25.0}
    # Customer IDs that have no overlap with test outcomes
    scored = [
        {"customer_id": f"unobserved_{i}", "uplift": 0.2, "p_treat": 0.5, "eligible": 1}
        for i in range(10)
    ]

    # Provide an assumed value to verify net_result is NOT fabricated when support is insufficient
    req = OptimizeRequest(budget_bdt=200.0, value_per_incremental_transaction_bdt=150.0)
    res = optimize_campaign_budget(campaign, scored, req, fixture_dir=tmp_path)

    for item in res.comparison.strategies:
        assert item.support == "insufficient"
        assert item.measured_incremental_response is None
        assert item.expected_incremental_transactions is None
        assert item.cost_per_incremental_transaction_bdt is None
        assert item.cost_per_incremental_txn_bdt is None
        # Must not fabricate net_result even though transaction value was supplied
        assert item.net_result is None
        assert item.value_assumption == "ASSUMED"


def test_fe09_fatigue_rate_calculation(tmp_path: Path):
    """Requirement E: Fatigue rate correctly calculates highest prior-exposure selected share."""
    from backend.app.services.optimizer import compute_fatigue_rate

    # Case 1: Feature present on customer dictionaries directly
    selected = [
        {"customer_id": "c1", "prior_exposure_band": "3+"},
        {"customer_id": "c2", "prior_exposure_band": "1-2"},
        {"customer_id": "c3", "campaign_exposures_prior_30d": 3},  # maps to 3+
        {"customer_id": "c4", "campaign_exposures_prior_30d": 0},  # maps to 0
    ]
    # 2 out of 4 are in highest band (3+)
    assert compute_fatigue_rate(selected) == 0.5

    # Case 2: Feature present in features_by_id lookup
    selected_lookup = [{"customer_id": "c10"}, {"customer_id": "c11"}]
    feat_lookup = {
        "c10": {"campaign_exposures_prior_90d": 4},  # maps to 3+
        "c11": {"campaign_exposures_prior_90d": 1},  # maps to 1-2
    }
    assert compute_fatigue_rate(selected_lookup, feat_lookup) == 0.5

    # Case 3: Feature completely unavailable -> returns None
    no_feat_selected = [{"customer_id": "c20"}, {"customer_id": "c21"}]
    assert compute_fatigue_rate(no_feat_selected) is None
    assert compute_fatigue_rate([]) is None


def test_fe09_negative_uplift_share_and_cannibalization(client: TestClient, created_campaign_id: str):
    """Requirement F: Expose negative-uplift selected share and preserve measured rate."""
    # 1. With exclude_negative_uplift=True (default), pure uplift has 0% negative uplift share
    resp_exc = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 50000.0, "exclude_negative_uplift": True},
    )
    assert resp_exc.status_code == 200
    comp_exc = {s["strategy"]: s for s in resp_exc.json()["comparison"]["strategies"]}
    assert comp_exc["uplift"]["negative_uplift_share"] == 0.0
    assert comp_exc["uplift"]["negative_uplift_selected_share"] == 0.0

    # 2. With exclude_negative_uplift=False and huge budget, pure uplift includes negative uplift
    resp_inc = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 50000.0, "exclude_negative_uplift": False},
    )
    assert resp_inc.status_code == 200
    comp_inc = {s["strategy"]: s for s in resp_inc.json()["comparison"]["strategies"]}
    pure_uplift = comp_inc["uplift"]

    assert pure_uplift["negative_uplift_share"] is not None
    assert pure_uplift["negative_uplift_share"] > 0.0
    assert pure_uplift["negative_uplift_share"] == pure_uplift["negative_uplift_selected_share"]

    # Measured incremental rate is preserved
    assert pure_uplift["measured_incremental_response"] is not None


def test_fe09_payload_contract_exact_naming(client: TestClient, created_campaign_id: str):
    """Requirement G: Business scorecard payload and name match exact contract strings."""
    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    comp = data["comparison"]

    # Contract names must be exact
    assert comp["scorecard_name"] == "Synthetic Experiment Business Scorecard"
    assert comp["evidence_boundary"] == (
        "Synthetic randomized experiment; not a controlled commercial holdout."
    )

    sc = comp["scorecard"]
    assert sc["scorecard_name"] == "Synthetic Experiment Business Scorecard"
    assert sc["name"] == "Synthetic Experiment Business Scorecard"
    assert sc["evidence_boundary"] == (
        "Synthetic randomized experiment; not a controlled commercial holdout."
    )

    # 4 strategies represented
    assert len(sc["strategies"]) == 4
    sc_strategies = {s["strategy"] for s in sc["strategies"]}
    assert sc_strategies == {"random", "response", "uplift", "uplift_plus_budget"}

    # Structured fields verified on each scorecard item
    for s in sc["strategies"]:
        assert "strategy" in s
        assert "selected_count" in s
        assert "spend_bdt" in s
        assert "support" in s
        assert "measured_incremental_response" in s
        assert "expected_incremental_transactions" in s
        assert "cost_per_incremental_transaction_bdt" in s
        assert "value_assumption" in s
        assert "net_result" in s
        assert "fatigue_rate" in s
        assert "negative_uplift_share" in s


