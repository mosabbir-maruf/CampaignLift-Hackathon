"""Unit and integration tests for Explanation API.

Canonical planning sources:
- planning/backend_plan.md
- planning/ml_plan.md
- tasks/assaduzzaman/21_explanation_api.md
- backend/openapi.yaml
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import CustomerExplanationResponse
from backend.app.services.explain import (
    determine_reason_code,
    generate_template_text,
    explain_customer,
    CustomerNotFoundError,
)
from backend.app.services.inference import ForbiddenColumnError
from backend.app.settings import Settings, get_settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings fixture using temporary SQLite DB and real fixture data/artifacts."""
    db_file = tmp_path / "test_explain.db"
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
        "incentive_value": 20.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 1000.0,
        "channel": "push",
    }
    resp = client.post("/api/v1/campaigns", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_reason_code_deterministic_rules():
    """Verify exact rule thresholds for the four canonical reason codes."""
    # 1. likely_without_offer: p_control >= 0.5 and uplift < 0.02
    assert determine_reason_code(p_treat=0.72, p_control=0.70, uplift=0.01) == "likely_without_offer"
    assert determine_reason_code(p_treat=0.60, p_control=0.65, uplift=-0.05) == "likely_without_offer"

    # 2. incremental_candidate: uplift >= 0.02
    assert determine_reason_code(p_treat=0.60, p_control=0.35, uplift=0.25) == "incremental_candidate"
    assert determine_reason_code(p_treat=0.42, p_control=0.40, uplift=0.02) == "incremental_candidate"

    # 3. negative_uplift: uplift < 0 and p_control < 0.5
    assert determine_reason_code(p_treat=0.20, p_control=0.30, uplift=-0.10) == "negative_uplift"

    # 4. weak_response: both probabilities low and uplift near zero (0 <= uplift < 0.02, p_control < 0.5)
    assert determine_reason_code(p_treat=0.21, p_control=0.20, uplift=0.01) == "weak_response"
    assert determine_reason_code(p_treat=0.10, p_control=0.10, uplift=0.0) == "weak_response"


def test_acceptance_fixture_customer_likely_without_offer(client: TestClient, created_campaign_id: str):
    """Validation & Acceptance Criteria: A fixture customer with high p_control and low uplift receives likely_without_offer."""
    # Customer C00000001 in fixture has p_control ~ 0.70 (> 0.50) and uplift ~ -0.055 (< 0.02)
    resp = client.get(f"/api/v1/campaigns/{created_campaign_id}/customers/C00000001/explanation")
    assert resp.status_code == 200
    data = resp.json()

    assert data["customer_id"] == "C00000001"
    assert data["p_control"] >= 0.50
    assert data["uplift"] < 0.02
    assert data["reason_code"] == "likely_without_offer"

    # Template text verification
    assert "Reason code: likely_without_offer" in data["template_text"]
    assert "Control probability is" in data["template_text"]
    assert "Treated probability is" in data["template_text"]
    assert "Estimated uplift is" in data["template_text"]
    assert "Largest feature differences:" in data["template_text"]


def test_all_reason_codes_represented_on_fixture(client: TestClient, created_campaign_id: str):
    """Verify that multiple reason codes can be retrieved from fixture customers."""
    seen_codes = set()
    sample_cids = ["C00000001", "C00000002", "C00000003", "C00000004", "C00000005"]

    for cid in sample_cids:
        resp = client.get(f"/api/v1/campaigns/{created_campaign_id}/customers/{cid}/explanation")
        if resp.status_code == 200:
            seen_codes.add(resp.json()["reason_code"])

    assert len(seen_codes) >= 2


def test_feature_contributions_grounded_and_no_leakage(client: TestClient, created_campaign_id: str):
    """Contributions are non-empty, sorted by absolute value, and free of forbidden ground-truth columns."""
    resp = client.get(f"/api/v1/campaigns/{created_campaign_id}/customers/C00000001/explanation")
    assert resp.status_code == 200
    data = resp.json()

    contribs = data["feature_contributions"]
    assert len(contribs) > 0

    # Verify sorting by magnitude
    magnitudes = [abs(c["contribution"]) for c in contribs]
    assert magnitudes == sorted(magnitudes, reverse=True)

    # Verify no causal leakage columns
    forbidden = {"true_uplift", "p_y_treat", "p_y_control", "natural_transaction_propensity"}
    for c in contribs:
        assert c["name"] not in forbidden
        assert isinstance(c["value"], str)
        assert isinstance(c["contribution"], float)

    # Verify features mentioned in template_text are present in contribs
    template_text = data["template_text"]
    diff_prefix = "Largest feature differences: "
    if diff_prefix in template_text:
        diff_part = template_text.split(diff_prefix)[1].rstrip(".")
        if diff_part != "none":
            for item in diff_part.split(", "):
                feat_name = item.split(" (")[0]
                assert any(c["name"] == feat_name for c in contribs)


def test_customer_not_found(client: TestClient, created_campaign_id: str):
    """Requesting explanation for nonexistent customer returns 404 with customer_not_found."""
    resp = client.get(f"/api/v1/campaigns/{created_campaign_id}/customers/C99999999/explanation")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "customer_not_found"


def test_campaign_not_found(client: TestClient):
    """Requesting explanation for nonexistent campaign returns 404 with campaign_not_found."""
    resp = client.get("/api/v1/campaigns/camp_nonexistent_99/customers/C00000001/explanation")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "campaign_not_found"


def test_explain_customer_direct_function(test_settings: Settings):
    """Direct invocation of explain_customer service function."""
    campaign_dict = {
        "id": "direct_test_camp",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 20.0,
        "incentive_cost_bdt": 25.0,
    }
    explanation = explain_customer(
        campaign=campaign_dict,
        customer_id="C00000001",
        settings=test_settings,
    )
    assert isinstance(explanation, CustomerExplanationResponse)
    assert explanation.customer_id == "C00000001"
    assert explanation.reason_code in ("likely_without_offer", "incremental_candidate", "weak_response", "negative_uplift")
