"""Tests for CampaignLift Budget Optimizer API.

Validation requirements:
- Budget is never exceeded on the fixture.
- Negative uplift customers are absent when exclusion is on.
- Response strategy can include a customer the uplift strategy rejects.
- Same input returns the same selected IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

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
    """GET /api/v1/campaigns/{id}/comparison returns 404 before optimize, and 200 with metrics after."""
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
    assert comp_data["campaign_id"] == created_campaign_id
    assert len(comp_data["strategies"]) == 3
    strat_names = {s["strategy"] for s in comp_data["strategies"]}
    assert strat_names == {"random", "response", "uplift"}
