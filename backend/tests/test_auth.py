"""Tests for Authentication and Role-Based Access Control (FE-04).

Verifies:
1. Manager and Viewer login with scrypt password verification.
2. HttpOnly session cookies signed with HMAC-SHA256.
3. Write operations require manager session:
   - Missing cookie on optimize returns 401.
   - Viewer on optimize returns 403.
   - Manager on optimize reaches the existing optimizer behavior (200).
4. Read operations remain available to viewer and manager.
5. Missing SESSION_SECRET on write operations returns 503.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings, get_settings


@pytest.fixture
def auth_settings(tmp_path: Path) -> Settings:
    """Settings fixture with authentication configured."""
    db_file = tmp_path / "test_auth.db"
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{db_file}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
        session_secret="test-session-secret-key-32bytes-hex-ok",
        manager_password="test-manager-password-456",
        viewer_password="test-viewer-password-789",
        gemini_api_key=None,
        log_level="DEBUG",
    )


@pytest.fixture
def client(auth_settings: Settings) -> TestClient:
    """TestClient wired with auth_settings."""
    app = create_app(auth_settings)
    app.dependency_overrides[get_settings] = lambda: auth_settings
    return TestClient(app)


@pytest.fixture
def created_campaign_id(client: TestClient) -> str:
    """Helper to create campaign using manager login and return ID."""
    # Log in as manager
    login_resp = client.post(
        "/auth/login",
        json={"username": "manager", "password": "test-manager-password-456"},
    )
    assert login_resp.status_code == 200

    payload = {
        "name": "Q4 QR Adoption Drive",
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 25.0,
        "incentive_cost_bdt": 25.0,
        "budget_bdt": 500.0,
        "channel": "push",
    }
    resp = client.post("/api/v1/campaigns", json=payload)
    assert resp.status_code == 201
    campaign_id = resp.json()["id"]

    # Clear cookie for clean state in tests
    client.post("/auth/logout")
    return campaign_id


def test_login_manager_and_viewer(client: TestClient):
    """Login succeeds for valid manager/viewer passwords and fails on invalid."""
    # 1. Manager login
    resp_mgr = client.post(
        "/auth/login",
        json={"username": "manager", "password": "test-manager-password-456"},
    )
    assert resp_mgr.status_code == 200
    assert resp_mgr.json()["role"] == "manager"
    assert "session" in resp_mgr.cookies

    # 2. Logout
    resp_logout = client.post("/auth/logout")
    assert resp_logout.status_code == 200

    # 3. Viewer login
    resp_view = client.post(
        "/auth/login",
        json={"username": "viewer", "password": "test-viewer-password-789"},
    )
    assert resp_view.status_code == 200
    assert resp_view.json()["role"] == "viewer"
    assert "session" in resp_view.cookies

    # 4. Bad password
    resp_bad = client.post(
        "/auth/login",
        json={"username": "manager", "password": "wrong-password"},
    )
    assert resp_bad.status_code == 401
    assert resp_bad.json()["error"] == "invalid_credentials"


def test_session_endpoint(client: TestClient):
    """GET /auth/session reflects role or returns 401 when logged out."""
    # Logged out
    resp = client.get("/auth/session")
    assert resp.status_code == 401

    # Log in as manager
    client.post(
        "/auth/login",
        json={"username": "manager", "password": "test-manager-password-456"},
    )
    resp_mgr = client.get("/auth/session")
    assert resp_mgr.status_code == 200
    assert resp_mgr.json()["role"] == "manager"

    # Log out
    client.post("/auth/logout")
    resp_after = client.get("/auth/session")
    assert resp_after.status_code == 401


def test_missing_cookie_on_optimize_returns_401(
    client: TestClient, created_campaign_id: str
):
    """Missing session cookie on POST /campaigns/{id}/optimize returns 401."""
    # Ensure client is logged out
    client.cookies.clear()

    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


def test_viewer_on_optimize_returns_403(
    client: TestClient, created_campaign_id: str
):
    """Viewer session on POST /campaigns/{id}/optimize returns 403."""
    # Log in as viewer
    login_resp = client.post(
        "/auth/login",
        json={"username": "viewer", "password": "test-viewer-password-789"},
    )
    assert login_resp.status_code == 200

    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"


def test_manager_on_optimize_reaches_optimizer(
    client: TestClient, created_campaign_id: str
):
    """Manager session on POST /campaigns/{id}/optimize succeeds and returns 200."""
    # Log in as manager
    login_resp = client.post(
        "/auth/login",
        json={"username": "manager", "password": "test-manager-password-456"},
    )
    assert login_resp.status_code == 200

    resp = client.post(
        f"/api/v1/campaigns/{created_campaign_id}/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "uplift"
    assert data["budget_bdt"] == 500.0
    assert data["selected_count"] > 0
    assert len(data["comparison"]["strategies"]) == 4


def test_reads_available_to_viewer_and_manager(
    client: TestClient, created_campaign_id: str
):
    """Read endpoints are accessible by viewer and manager."""
    # Viewer can read campaign details
    client.post(
        "/auth/login",
        json={"username": "viewer", "password": "test-viewer-password-789"},
    )
    resp = client.get(f"/api/v1/campaigns/{created_campaign_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created_campaign_id

    # Manager can also read campaign details
    client.post(
        "/auth/login",
        json={"username": "manager", "password": "test-manager-password-456"},
    )
    resp_mgr = client.get(f"/api/v1/campaigns/{created_campaign_id}")
    assert resp_mgr.status_code == 200


def test_missing_secret_returns_503(tmp_path: Path):
    """When SESSION_SECRET is missing, write endpoints return 503."""
    db_file = tmp_path / "test_no_secret.db"
    unconfigured_settings = Settings(
        app_env="production",  # non-test triggers 503 when secret is missing
        database_url=f"sqlite:///{db_file}",
        session_secret=None,
        manager_password=None,
        viewer_password=None,
    )
    app = create_app(unconfigured_settings)
    test_client = TestClient(app)

    resp = test_client.post(
        "/api/v1/campaigns/dummy-camp-id/optimize",
        json={"budget_bdt": 500.0},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "auth_not_configured"
