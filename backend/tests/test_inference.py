"""Tests for CampaignLift Inference API (Step 18).

Canonical validation requirements:
- tasks/assaduzzaman/18_inference_api.md:
  "Validation: API test on the fixture returns finite uplift and no forbidden field."
  "Acceptance criteria: API test on the fixture returns finite uplift and no forbidden field."
- Failure condition: Returning true_uplift.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.inference import FORBIDDEN_COLUMNS
from backend.app.settings import Settings, get_settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings fixture using temporary SQLite DB and real fixture data/artifacts."""
    db_file = tmp_path / "test_inference.db"
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
def sample_campaign_payload() -> Dict[str, Any]:
    """Valid campaign create payload matching OpenAPI schema."""
    return {
        "name": "Q4 Merchant QR Adoption Drive",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 25.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 50000.0,
        "channel": "push",
    }


def test_create_campaign_success(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """Campaign creation persists valid OpenAPI fields and returns 201 with generated id."""
    resp = client.post("/api/v1/campaigns", json=sample_campaign_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == sample_campaign_payload["name"]
    assert data["objective"] == sample_campaign_payload["objective"]
    assert data["offer_type"] == sample_campaign_payload["offer_type"]
    assert data["incentive_value"] == 25.0
    assert data["incentive_cost_bdt"] == 25.0
    assert data["budget_bdt"] == 50000.0
    assert data["channel"] == "push"
    assert data["id"].startswith("camp_")
    assert "created_at" in data


def test_create_campaign_rejects_customer_upload(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """Creating a campaign must reject any payload attempting customer list upload with 400."""
    # Attempt 1: 'customers' key
    payload_with_customers = dict(sample_campaign_payload)
    payload_with_customers["customers"] = ["C00000001", "C00000004"]
    resp1 = client.post("/api/v1/campaigns", json=payload_with_customers)
    assert resp1.status_code == 400
    assert resp1.json()["error"] == "customer_upload_not_allowed"

    # Attempt 2: 'customer_list' key
    payload_with_list = dict(sample_campaign_payload)
    payload_with_list["customer_list"] = [{"id": "C00000001"}]
    resp2 = client.post("/api/v1/campaigns", json=payload_with_list)
    assert resp2.status_code == 400
    assert resp2.json()["error"] == "customer_upload_not_allowed"


def test_create_campaign_validation_failure(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """Invalid campaign attributes must be rejected with 400."""
    bad_payload = dict(sample_campaign_payload)
    bad_payload["budget_bdt"] = -100.0  # Budget must be strictly > 0
    resp = client.post("/api/v1/campaigns", json=bad_payload)
    assert resp.status_code == 400
    assert resp.json()["error"] == "validation_error"


def test_get_campaign_by_id(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """GET /api/v1/campaigns/{id} retrieves saved campaign; returns 404 for missing id."""
    # Create
    create_resp = client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    # Read back
    get_resp = client.get(f"/api/v1/campaigns/{camp_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == camp_id
    assert get_resp.json()["name"] == sample_campaign_payload["name"]

    # Read non-existent
    missing_resp = client.get("/api/v1/campaigns/nonexistent_camp_id")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"] == "campaign_not_found"


def test_score_campaign_fixture_returns_finite_uplift_and_no_forbidden_field(
    client: TestClient, sample_campaign_payload: Dict[str, Any]
):
    """Validation standard: API test on fixture returns finite uplift, proper ranks, and zero forbidden fields."""
    # 1. Create campaign
    create_resp = client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    # 2. Execute scoring on fixture
    score_resp = client.post(f"/api/v1/campaigns/{camp_id}/score?limit=200&offset=0")
    assert score_resp.status_code == 200
    data = score_resp.json()

    # Verify run metadata
    assert data["campaign_id"] == camp_id
    assert data["run_id"].startswith("run_")
    assert data["total_eligible"] == 103  # fixture_v1 has 103 rows
    assert data["total_scored"] == 103
    assert data["total_count"] == 103
    assert len(data["items"]) == 103

    # Verify deciles
    assert len(data["uplift_deciles"]) == 10
    total_decile_customers = sum(d["customer_count"] for d in data["uplift_deciles"])
    assert total_decile_customers == 103

    # Allowed item fields according to OpenAPI CustomerScoreItem
    allowed_item_fields = {
        "customer_id",
        "eligible",
        "p_treat",
        "p_control",
        "uplift",
        "response_rank",
        "uplift_rank",
    }

    uplift_ranks = []
    response_ranks = []

    for item in data["items"]:
        # Field allowlist check
        item_keys = set(item.keys())
        assert item_keys == allowed_item_fields, f"Unexpected or missing item keys: {item_keys}"

        # CRITICAL ANTI-LEAKAGE: Assert no forbidden field exists in the item
        assert "true_uplift" not in item, "CRITICAL FAILURE: 'true_uplift' returned in customer score item!"
        for forbidden in FORBIDDEN_COLUMNS:
            assert forbidden not in item, f"CRITICAL FAILURE: Forbidden column '{forbidden}' returned in score item!"

        # Finite real numbers verification
        assert math.isfinite(item["p_treat"]), f"Non-finite p_treat: {item['p_treat']}"
        assert math.isfinite(item["p_control"]), f"Non-finite p_control: {item['p_control']}"
        assert math.isfinite(item["uplift"]), f"Non-finite uplift: {item['uplift']}"

        # Probabilities bounded in [0, 1]
        assert 0.0 <= item["p_treat"] <= 1.0
        assert 0.0 <= item["p_control"] <= 1.0

        # Uplift identity: uplift == p_treat - p_control (within float precision)
        expected_uplift = round(item["p_treat"] - item["p_control"], 6)
        assert abs(item["uplift"] - expected_uplift) < 1e-4

        uplift_ranks.append(item["uplift_rank"])
        response_ranks.append(item["response_rank"])

    # Verify ranks are valid permutations 1..103
    assert sorted(uplift_ranks) == list(range(1, 104))
    assert sorted(response_ranks) == list(range(1, 104))


def test_score_campaign_pagination(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """Scoring route respects limit and offset pagination parameters."""
    create_resp = client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    # Page 1: limit 20, offset 0
    resp_p1 = client.post(f"/api/v1/campaigns/{camp_id}/score?limit=20&offset=0")
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert len(data_p1["items"]) == 20
    assert data_p1["items"][0]["uplift_rank"] == 1
    assert data_p1["items"][-1]["uplift_rank"] == 20

    # Page 2: limit 20, offset 20
    resp_p2 = client.post(f"/api/v1/campaigns/{camp_id}/score?limit=20&offset=20")
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) == 20
    assert data_p2["items"][0]["uplift_rank"] == 21
    assert data_p2["items"][-1]["uplift_rank"] == 40

    # Ensure no duplicate customer_ids across non-overlapping pages
    ids_p1 = {item["customer_id"] for item in data_p1["items"]}
    ids_p2 = {item["customer_id"] for item in data_p2["items"]}
    assert ids_p1.isdisjoint(ids_p2)


def test_score_campaign_rejects_customer_upload_body(client: TestClient, sample_campaign_payload: Dict[str, Any]):
    """POST /api/v1/campaigns/{id}/score rejects any customer upload in body with 400."""
    create_resp = client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    resp = client.post(
        f"/api/v1/campaigns/{camp_id}/score",
        json={"customers": ["C00000001", "C00000004"]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "customer_upload_not_allowed"


def test_score_campaign_not_found(client: TestClient):
    """Scoring a non-existent campaign returns 404."""
    resp = client.post("/api/v1/campaigns/missing_camp/score")
    assert resp.status_code == 404
    assert resp.json()["error"] == "campaign_not_found"


def test_score_campaign_refuses_feature_mismatch(
    tmp_path: Path, sample_campaign_payload: Dict[str, Any]
):
    """Refuse a feature mismatch: missing required columns returns HTTP 503."""
    # Create invalid feature file missing several required columns
    bad_features_file = tmp_path / "bad_features.json"
    bad_data = [
        {
            "customer_id": "C001",
            "tenure_days": 100,
            # Missing txn_count_30d, txn_count_90d, age_band, etc.
        }
    ]
    with open(bad_features_file, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)

    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'mismatch.db'}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path=str(bad_features_file),
    )

    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    create_resp = test_client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    score_resp = test_client.post(f"/api/v1/campaigns/{camp_id}/score")
    assert score_resp.status_code == 503
    assert score_resp.json()["error"] == "feature_mismatch"
    assert "Missing required columns" in score_resp.json()["detail"]


def test_score_campaign_fails_when_model_missing(
    tmp_path: Path, sample_campaign_payload: Dict[str, Any]
):
    """Scoring returns 503 when model artifact path does not exist."""
    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'no_model.db'}",
        model_artifact_dir=str(tmp_path / "nonexistent_model"),
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
    )

    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    create_resp = test_client.post("/api/v1/campaigns", json=sample_campaign_payload)
    camp_id = create_resp.json()["id"]

    score_resp = test_client.post(f"/api/v1/campaigns/{camp_id}/score")
    assert score_resp.status_code == 503
    assert score_resp.json()["error"] == "not_ready"
