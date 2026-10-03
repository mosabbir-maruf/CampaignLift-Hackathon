"""Unit and integration tests for Experiment Intelligence API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import ExperimentSummaryResponse
from backend.app.services.experiment import (
    compute_experiment_summary,
    derive_activity_band,
    derive_exposure_band,
)
from backend.app.services.inference import ForbiddenColumnError
from backend.app.main import create_app
from backend.app.settings import Settings, get_settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings fixture using temporary SQLite DB and real fixture data/artifacts."""
    db_file = tmp_path / "test_experiment.db"
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
    """Fixture that creates a valid campaign in the database."""
    campaign_payload = {
        "name": "QR Experiment Campaign",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 20.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 1000.0,
        "channel": "push",
    }
    resp = client.post("/api/v1/campaigns", json=campaign_payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_hand_calculation_tiny_table():
    """Fixture/tiny table response matches exact hand calculation."""
    # 4 treated customers: 3 successes (1, 1, 1, 0) -> rate = 3/4 = 0.75
    # 4 control customers: 1 success   (1, 0, 0, 0) -> rate = 1/4 = 0.25
    # Incremental = 0.75 - 0.25 = 0.50
    exposures = [
        {"customer_id": "T1", "treatment": 1},
        {"customer_id": "T2", "treatment": 1},
        {"customer_id": "T3", "treatment": 1},
        {"customer_id": "T4", "treatment": 1},
        {"customer_id": "C1", "treatment": 0},
        {"customer_id": "C2", "treatment": 0},
        {"customer_id": "C3", "treatment": 0},
        {"customer_id": "C4", "treatment": 0},
    ]
    outcomes = [
        {"customer_id": "T1", "y_transacted": 1},
        {"customer_id": "T2", "y_transacted": 1},
        {"customer_id": "T3", "y_transacted": 1},
        {"customer_id": "T4", "y_transacted": 0},
        {"customer_id": "C1", "y_transacted": 1},
        {"customer_id": "C2", "y_transacted": 0},
        {"customer_id": "C3", "y_transacted": 0},
        {"customer_id": "C4", "y_transacted": 0},
    ]
    features = [
        {"customer_id": "T1", "region_code": "DHK"},
        {"customer_id": "T2", "region_code": "DHK"},
        {"customer_id": "T3", "region_code": "DHK"},
        {"customer_id": "T4", "region_code": "DHK"},
        {"customer_id": "C1", "region_code": "DHK"},
        {"customer_id": "C2", "region_code": "DHK"},
        {"customer_id": "C3", "region_code": "DHK"},
        {"customer_id": "C4", "region_code": "DHK"},
    ]

    res = compute_experiment_summary(
        campaign_id="test_tiny",
        exposures=exposures,
        outcomes=outcomes,
        features=features,
        split_filter="all",
        min_support=30,
    )

    assert res.total_treated == 4
    assert res.total_control == 4
    assert res.treated_outcome_rate == 0.75
    assert res.control_outcome_rate == 0.25
    assert res.overall_incremental_outcome == 0.50

    # Since slice DHK has 4 treated and 4 control (< 30), support MUST be insufficient and rates None
    dhk_slice = next((s for s in res.slices if s.slice_name == "region_code" and s.slice_value == "DHK"), None)
    assert dhk_slice is not None
    assert dhk_slice.support == "insufficient"
    assert dhk_slice.treated_outcome_rate is None
    assert dhk_slice.control_outcome_rate is None
    assert dhk_slice.incremental_outcome is None


def test_support_rule_nulls_under_minimum_support():
    """Slices with fewer than 30 treated or 30 control must have null rates, not filled from overall rate."""
    # 29 treated and 30 control (treated fails >= 30 threshold)
    exposures = [{"customer_id": f"T{i}", "treatment": 1} for i in range(29)] + [
        {"customer_id": f"C{i}", "treatment": 0} for i in range(30)
    ]
    outcomes = [{"customer_id": f"T{i}", "y_transacted": 1} for i in range(29)] + [
        {"customer_id": f"C{i}", "y_transacted": 0} for i in range(30)
    ]
    features = [{"customer_id": f"T{i}", "kyc_level": "verified"} for i in range(29)] + [
        {"customer_id": f"C{i}", "kyc_level": "verified"} for i in range(30)
    ]

    res = compute_experiment_summary(
        campaign_id="test_support_threshold",
        exposures=exposures,
        outcomes=outcomes,
        features=features,
        split_filter="all",
        min_support=30,
    )

    slice_item = res.slices[0]
    assert slice_item.support == "insufficient"
    assert slice_item.treated_outcome_rate is None
    assert slice_item.control_outcome_rate is None
    assert slice_item.incremental_outcome is None

    # CRITICAL: Verify it did NOT copy the overall rate
    assert res.treated_outcome_rate == 1.0
    assert slice_item.treated_outcome_rate is None


def test_support_rule_computes_sufficient_slice():
    """Slices with >= 30 treated AND >= 30 control compute exact non-null rates."""
    # 35 treated: 21 successes -> 21/35 = 0.60
    # 35 control: 7 successes  -> 7/35 = 0.20
    # Incremental: 0.60 - 0.20 = 0.40
    exposures = [{"customer_id": f"T{i}", "treatment": 1} for i in range(35)] + [
        {"customer_id": f"C{i}", "treatment": 0} for i in range(35)
    ]
    outcomes = (
        [{"customer_id": f"T{i}", "y_transacted": 1 if i < 21 else 0} for i in range(35)]
        + [{"customer_id": f"C{i}", "y_transacted": 1 if i < 7 else 0} for i in range(35)]
    )
    features = [{"customer_id": f"T{i}", "region_code": "CTG"} for i in range(35)] + [
        {"customer_id": f"C{i}", "region_code": "CTG"} for i in range(35)
    ]

    res = compute_experiment_summary(
        campaign_id="test_sufficient",
        exposures=exposures,
        outcomes=outcomes,
        features=features,
        split_filter="all",
        min_support=30,
    )

    ctg_slice = next((s for s in res.slices if s.slice_name == "region_code" and s.slice_value == "CTG"), None)
    assert ctg_slice is not None
    assert ctg_slice.support == "sufficient"
    assert ctg_slice.treated_outcome_rate == 0.6
    assert ctg_slice.control_outcome_rate == 0.2
    assert ctg_slice.incremental_outcome == 0.4


def test_derived_bands_utility():
    """Verify derivation of activity_band and exposure_band."""
    assert derive_activity_band(0) == "0"
    assert derive_activity_band(3) == "1-4"
    assert derive_activity_band(10) == "5+"
    assert derive_activity_band(None) == "0"

    assert derive_exposure_band(0) == "0"
    assert derive_exposure_band(2) == "1-2"
    assert derive_exposure_band(5) == "3+"
    assert derive_exposure_band(None) == "0"


def test_get_experiment_endpoint_on_fixture(client: TestClient, created_campaign_id: str):
    """GET /api/v1/campaigns/{id}/experiment returns valid response on fixture dataset."""
    resp = client.get(f"/api/v1/campaigns/{created_campaign_id}/experiment")
    assert resp.status_code == 200
    data = resp.json()

    assert data["campaign_id"] == created_campaign_id
    assert data["total_treated"] > 0
    assert data["total_control"] > 0
    assert 0.0 <= data["treated_outcome_rate"] <= 1.0
    assert 0.0 <= data["control_outcome_rate"] <= 1.0
    expected_incremental = round(data["treated_outcome_rate"] - data["control_outcome_rate"], 4)
    assert abs(data["overall_incremental_outcome"] - expected_incremental) < 1e-4
    assert isinstance(data["slices"], list)
    assert len(data["slices"]) > 0


def test_get_experiment_with_split_query(client: TestClient, created_campaign_id: str):
    """GET /api/v1/campaigns/{id}/experiment supports split filtering e.g. test vs all."""
    # 1. Test split
    resp_test = client.get(f"/api/v1/campaigns/{created_campaign_id}/experiment?split=test")
    assert resp_test.status_code == 200
    data_test = resp_test.json()
    assert data_test["total_treated"] == 6
    assert data_test["total_control"] == 10
    assert data_test["treated_outcome_rate"] == 0.6667
    assert data_test["control_outcome_rate"] == 0.5000
    assert data_test["overall_incremental_outcome"] == 0.1667

    # 2. All fixture rows
    resp_all = client.get(f"/api/v1/campaigns/{created_campaign_id}/experiment?split=all")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert data_all["total_treated"] == 49
    assert data_all["total_control"] == 54
    assert data_all["treated_outcome_rate"] == 0.5714
    assert data_all["control_outcome_rate"] == 0.5185
    assert data_all["overall_incremental_outcome"] == 0.0529

    # Check sufficient slices on all fixture rows
    verified_slice = next(
        (s for s in data_all["slices"] if s["slice_name"] == "kyc_level" and s["slice_value"] == "verified"),
        None,
    )
    assert verified_slice is not None
    assert verified_slice["support"] == "sufficient"
    assert verified_slice["treated_count"] == 33
    assert verified_slice["control_count"] == 43
    assert verified_slice["treated_outcome_rate"] is not None
    assert verified_slice["control_outcome_rate"] is not None
    assert verified_slice["incremental_outcome"] is not None


def test_get_experiment_campaign_not_found(client: TestClient):
    """Requesting experiment for a non-existent campaign returns 404."""
    resp = client.get("/api/v1/campaigns/nonexistent_camp_999/experiment")
    assert resp.status_code == 404
    assert resp.json()["error"] == "campaign_not_found"


def test_both_arms_required():
    """Experiment summary computation refuses dataset missing one of the arms."""
    exposures_only_treat = [
        {"customer_id": "T1", "treatment": 1},
        {"customer_id": "T2", "treatment": 1},
    ]
    outcomes = [
        {"customer_id": "T1", "y_transacted": 1},
        {"customer_id": "T2", "y_transacted": 0},
    ]
    with pytest.raises(ValueError, match="Both treatment and control arms must be present"):
        compute_experiment_summary(
            campaign_id="c_err",
            exposures=exposures_only_treat,
            outcomes=outcomes,
            split_filter="all",
        )


def test_causal_leakage_forbidden_columns_refused():
    """Passing forbidden causal leakage columns into features raises ForbiddenColumnError."""
    exposures = [
        {"customer_id": "T1", "treatment": 1},
        {"customer_id": "C1", "treatment": 0},
    ]
    outcomes = [
        {"customer_id": "T1", "y_transacted": 1},
        {"customer_id": "C1", "y_transacted": 0},
    ]
    features_leaked = [
        {"customer_id": "T1", "region_code": "DHK", "true_uplift": 0.12},
        {"customer_id": "C1", "region_code": "DHK", "true_uplift": -0.05},
    ]
    with pytest.raises(ForbiddenColumnError, match="CRITICAL CAUSAL LEAKAGE"):
        compute_experiment_summary(
            campaign_id="c_leak",
            exposures=exposures,
            outcomes=outcomes,
            features=features_leaked,
            split_filter="all",
        )
