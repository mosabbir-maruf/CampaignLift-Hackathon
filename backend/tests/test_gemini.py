"""Unit and integration tests for Gemini Copilot adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_connection
from backend.app.main import create_app
from backend.app.schemas import CopilotResponse
from backend.app.services.gemini import (
    CopilotDisabledError,
    CopilotUnavailableError,
    SYSTEM_INSTRUCTION,
    build_run_context,
    extract_customer_id_from_text,
    query_copilot,
    recursively_assert_no_forbidden_leakage,
)
from backend.app.settings import Settings, get_settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Settings fixture with temporary SQLite DB and real fixture data/artifacts."""
    db_file = tmp_path / "test_gemini.db"
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{db_file}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
        gemini_api_key=None,  # Disabled by default
        log_level="DEBUG",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """TestClient wired with test_settings."""
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    return TestClient(app)


@pytest.fixture
def scored_campaign_and_run(client: TestClient) -> tuple[str, str]:
    """Helper to create campaign and run score run to produce verified run_id."""
    campaign_payload = {
        "name": "Q4 QR Adoption Drive",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 20.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 1000.0,
        "channel": "push",
    }
    create_resp = client.post("/api/v1/campaigns", json=campaign_payload)
    assert create_resp.status_code == 201
    campaign_id = create_resp.json()["id"]

    # Score campaign
    score_resp = client.post(f"/api/v1/campaigns/{campaign_id}/score?limit=200")
    assert score_resp.status_code == 200
    run_id = score_resp.json()["run_id"]

    return campaign_id, run_id


def test_validation_context_contains_fixture_uplift_and_not_true_uplift(
    test_settings: Settings,
    scored_campaign_and_run: tuple[str, str],
):
    """Validation & Acceptance Criteria: Context contains fixture uplift and strictly does NOT contain true_uplift."""
    campaign_id, run_id = scored_campaign_and_run
    conn = get_connection(test_settings)

    try:
        context, fields_used = build_run_context(
            run_id=run_id,
            campaign_id=campaign_id,
            question="Why was customer C00000001 selected?",
            conn=conn,
            settings=test_settings,
        )

        # 1. Assert context contains fixture uplift
        assert "customer_explanation" in context
        assert "uplift" in context["customer_explanation"]
        assert isinstance(context["customer_explanation"]["uplift"], float)
        assert context["customer_explanation"]["customer_id"] == "C00000001"
        assert "uplift_summary" in context

        # 2. Assert context does NOT contain true_uplift or other unobservable causal variables
        context_json_str = json.dumps(context).lower()
        assert "true_uplift" not in context_json_str
        assert "p_y_treat" not in context_json_str
        assert "p_y_control" not in context_json_str
        assert "natural_transaction_propensity" not in context_json_str

        # Recursive safety check raises no error
        recursively_assert_no_forbidden_leakage(context)
    finally:
        conn.close()


def test_customer_id_extraction_regex():
    """Extract customer IDs reliably from manager queries."""
    assert extract_customer_id_from_text("Why was customer C00000001 selected?") == "C00000001"
    assert extract_customer_id_from_text("Explain C12345 behavior") == "C12345"
    assert extract_customer_id_from_text("What is the budget for this campaign?") is None


def test_missing_api_key_returns_copilot_disabled(
    client: TestClient,
    scored_campaign_and_run: tuple[str, str],
):
    """Missing GEMINI_API_KEY returns HTTP 503 copilot_disabled."""
    campaign_id, run_id = scored_campaign_and_run

    resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/copilot",
        json={
            "question": "What is the expected uplift for this campaign?",
            "run_id": run_id,
        },
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"] == "copilot_disabled"


def test_mock_gemini_query_success(
    test_settings: Settings,
    scored_campaign_and_run: tuple[str, str],
):
    """Direct query_copilot with mock caller returns grounded answer and context fields."""
    campaign_id, run_id = scored_campaign_and_run
    conn = get_connection(test_settings)

    mock_answer = (
        "Customer C00000001 has an estimated control probability of 0.70 and treated probability "
        "of 0.65, giving an uplift of -0.05. Their reason code is likely_without_offer."
    )

    def mock_gemini_caller(prompt: str, system_instruction: str, **kwargs) -> str:
        assert SYSTEM_INSTRUCTION in system_instruction
        assert "Verified Run JSON Context" in prompt
        assert "C00000001" in prompt
        assert "true_uplift" not in prompt.lower()
        return mock_answer

    from backend.app.schemas import CopilotRequest

    req = CopilotRequest(
        question="Why was customer C00000001 categorized as likely_without_offer?",
        run_id=run_id,
    )

    try:
        copilot_resp = query_copilot(
            campaign_id=campaign_id,
            request=req,
            conn=conn,
            settings=test_settings,
            gemini_caller=mock_gemini_caller,
        )
        assert isinstance(copilot_resp, CopilotResponse)
        assert copilot_resp.answer == mock_answer
        assert "run_id" in copilot_resp.context_fields_used
        assert "customer_id" in copilot_resp.context_fields_used
        assert "uplift" in copilot_resp.context_fields_used
        assert copilot_resp.unavailable is False
    finally:
        conn.close()


def test_copilot_run_not_found(
    client: TestClient,
    scored_campaign_and_run: tuple[str, str],
):
    """Supplying a nonexistent run_id returns HTTP 404 run_not_found."""
    campaign_id, _ = scored_campaign_and_run

    resp = client.post(
        f"/api/v1/campaigns/{campaign_id}/copilot",
        json={
            "question": "What is the expected uplift?",
            "run_id": "nonexistent_run_9999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "run_not_found"


def test_copilot_campaign_not_found(client: TestClient):
    """Supplying a nonexistent campaign_id returns HTTP 404 campaign_not_found."""
    resp = client.post(
        "/api/v1/campaigns/nonexistent_camp_888/copilot",
        json={
            "question": "What is the expected uplift?",
            "run_id": "run_123",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "campaign_not_found"


def test_copilot_provider_unavailable(
    test_settings: Settings,
    scored_campaign_and_run: tuple[str, str],
):
    """When Gemini provider call fails, raises CopilotUnavailableError."""
    campaign_id, run_id = scored_campaign_and_run
    conn = get_connection(test_settings)

    def failing_caller(**kwargs) -> str:
        raise CopilotUnavailableError("Timeout contacting Gemini API")

    from backend.app.schemas import CopilotRequest

    req = CopilotRequest(
        question="What is the expected uplift?",
        run_id=run_id,
    )

    try:
        with pytest.raises(CopilotUnavailableError, match="Timeout contacting Gemini"):
            query_copilot(
                campaign_id=campaign_id,
                request=req,
                conn=conn,
                settings=test_settings,
                gemini_caller=failing_caller,
            )
    finally:
        conn.close()
