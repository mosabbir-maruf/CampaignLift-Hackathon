"""Tests for backend foundation: settings, db, /health, and /ready endpoints.

Canonical requirements:
- Step 17 in planning/master_project_plan.md
- tasks/assaduzzaman/17_backend_foundation.md
- planning/backend_plan.md
- backend/openapi.yaml
"""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.db import (
    check_database_writable,
    get_connection,
    get_db,
    get_sqlite_path,
    init_db,
)
from backend.app.main import create_app
from backend.app.settings import Settings, get_settings


@pytest.fixture
def valid_settings(tmp_path: Path) -> Settings:
    """Fixture providing valid settings pointing to real repo artifacts and temp sqlite db."""
    test_db_path = tmp_path / "test_campaignlift.db"
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{test_db_path}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
        gemini_api_key=None,
        gemini_model="gemini-2.5-flash",
        log_level="DEBUG",
    )


@pytest.fixture
def client(valid_settings: Settings) -> TestClient:
    """TestClient wired with valid settings."""
    app = create_app(valid_settings)
    app.dependency_overrides[get_settings] = lambda: valid_settings
    return TestClient(app)


def test_health_returns_200_ok(client: TestClient):
    """Liveness probe /health must return HTTP 200 with status ok and zero external checks."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}


def test_ready_returns_200_when_dependencies_valid(client: TestClient, valid_settings: Settings):
    """Readiness probe /ready returns HTTP 200 when model, feature table, and db are valid."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["model_loaded"] is True
    assert data["model_version"] == "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
    assert data["dataset_version"] == "cl-synth-ml_dev-20261006-8ad556a"
    assert data["feature_file_readable"] is True
    assert data["database_writable"] is True


def test_ready_returns_503_when_model_path_is_wrong(tmp_path: Path):
    """Readiness probe /ready must fail with 503 when model artifact directory does not exist."""
    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        model_artifact_dir=str(tmp_path / "nonexistent_model_dir"),
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
    )
    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    # 1. /ready must return 503 not ready
    ready_resp = test_client.get("/ready")
    assert ready_resp.status_code == 503
    ready_data = ready_resp.json()
    assert ready_data["error"] == "not_ready"
    assert "Model artifact not ready" in ready_data["detail"]

    # 2. /health must STILL return 200 OK (liveness must never depend on model path)
    health_resp = test_client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok"}


def test_ready_returns_503_when_metadata_json_missing(tmp_path: Path):
    """Readiness probe /ready must fail with 503 when metadata.json is missing in artifact dir."""
    incomplete_model_dir = tmp_path / "incomplete_model"
    incomplete_model_dir.mkdir()
    (incomplete_model_dir / "model.joblib").write_text("fake binary")

    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        model_artifact_dir=str(incomplete_model_dir),
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
    )
    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    ready_resp = test_client.get("/ready")
    assert ready_resp.status_code == 503
    assert ready_resp.json()["error"] == "not_ready"
    assert "Missing metadata.json" in ready_resp.json()["detail"]


def test_ready_returns_503_when_model_binary_missing(tmp_path: Path):
    """Readiness probe /ready must fail with 503 when model.joblib is missing in artifact dir."""
    incomplete_model_dir = tmp_path / "no_binary_model"
    incomplete_model_dir.mkdir()
    (incomplete_model_dir / "metadata.json").write_text('{"model_version": "v1"}')

    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        model_artifact_dir=str(incomplete_model_dir),
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
    )
    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    ready_resp = test_client.get("/ready")
    assert ready_resp.status_code == 503
    assert ready_resp.json()["error"] == "not_ready"
    assert "Missing model binary model.joblib" in ready_resp.json()["detail"]


def test_ready_returns_503_when_feature_table_missing(tmp_path: Path):
    """Readiness probe /ready must fail with 503 when feature table file does not exist."""
    bad_settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path=str(tmp_path / "nonexistent_features.json"),
    )
    app = create_app(bad_settings)
    app.dependency_overrides[get_settings] = lambda: bad_settings
    test_client = TestClient(app)

    ready_resp = test_client.get("/ready")
    assert ready_resp.status_code == 503
    assert ready_resp.json()["error"] == "not_ready"
    assert "Feature table not readable" in ready_resp.json()["detail"]


def test_ready_returns_503_when_database_not_writable(valid_settings: Settings):
    """Readiness probe /ready must fail with 503 when database is not writable."""
    app = create_app(valid_settings)
    app.dependency_overrides[get_settings] = lambda: valid_settings
    test_client = TestClient(app)

    with patch("backend.app.main.check_database_writable", return_value=False):
        ready_resp = test_client.get("/ready")
        assert ready_resp.status_code == 503
        assert ready_resp.json()["error"] == "not_ready"
        assert "Database is not writable" in ready_resp.json()["detail"]


def test_settings_environment_variable_override(monkeypatch):
    """Settings must properly read from environment variables."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("MODEL_ARTIFACT_DIR", "artifacts/custom_model")
    monkeypatch.setenv("FEATURE_TABLE_PATH", "data/custom_features.json")

    settings = Settings()
    assert settings.app_env == "production"
    assert settings.database_url == "sqlite:///./prod.db"
    assert settings.log_level == "WARNING"
    assert settings.model_artifact_dir == "artifacts/custom_model"
    assert settings.feature_table_path == "data/custom_features.json"


def test_db_session_and_writability(tmp_path: Path):
    """Database helper functions must successfully initialize, connect, and check write access."""
    db_file = tmp_path / "test_db.sqlite"
    custom_settings = Settings(database_url=f"sqlite:///{db_file}")

    assert check_database_writable(custom_settings) is True
    init_db(custom_settings)

    # Verify session generator
    gen = get_db(custom_settings)
    conn = next(gen)
    assert isinstance(conn, sqlite3.Connection)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "_health_check" in tables
    try:
        next(gen)
    except StopIteration:
        pass
