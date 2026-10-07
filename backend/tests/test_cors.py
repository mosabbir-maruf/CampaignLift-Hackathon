"""Tests for FE-03: Trusted-Origin CORS hardening."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import (
    DEFAULT_LOCAL_ORIGINS,
    Settings,
    get_settings,
    parse_trusted_origins,
)


@pytest.fixture
def cors_settings(tmp_path: Path) -> Settings:
    """Fixture providing settings configured with specific trusted origins."""
    test_db_path = tmp_path / "test_cors.db"
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{test_db_path}",
        model_artifact_dir="artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        dataset_version="cl-synth-ml_dev-20261006-8ad556a",
        feature_table_path="data/fixtures/fixture_v1/features.json",
        trusted_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://trusted-domain.com"],
    )


@pytest.fixture
def client(cors_settings: Settings) -> TestClient:
    """TestClient wired with cors_settings."""
    app = create_app(cors_settings)
    app.dependency_overrides[get_settings] = lambda: cors_settings
    return TestClient(app)


# ------------------------------------------------------------------------------
# A. Allowed origin tests
# ------------------------------------------------------------------------------

def test_cors_allowed_origin_simple_request(client: TestClient):
    """A request containing an explicitly configured trusted Origin receives CORS headers with credentials."""
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_second_allowed_origin_simple_request(client: TestClient):
    """All explicitly configured trusted origins are permitted with credentials enabled."""
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"

    response_custom = client.get("/health", headers={"Origin": "https://trusted-domain.com"})
    assert response_custom.status_code == 200
    assert response_custom.headers.get("access-control-allow-origin") == "https://trusted-domain.com"
    assert response_custom.headers.get("access-control-allow-credentials") == "true"


def test_cors_allowed_origin_preflight_request(client: TestClient):
    """Preflight OPTIONS request from an allowed origin receives appropriate CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allowed_methods
    assert "GET" in allowed_methods
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers


# ------------------------------------------------------------------------------
# B. Untrusted origin tests
# ------------------------------------------------------------------------------

def test_cors_untrusted_origin_rejected(client: TestClient):
    """A request from an untrusted/evil origin does NOT receive an Access-Control-Allow-Origin header."""
    response = client.get("/health", headers={"Origin": "http://evil.com"})
    assert response.status_code == 200
    # Must NOT permit evil.com
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_untrusted_origin_preflight_rejected(client: TestClient):
    """Preflight request from an untrusted origin does NOT receive an Access-Control-Allow-Origin header."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize(
    "untrusted_origin",
    [
        "http://localhost:3000",
        "http://evil-localhost:5173",
        "http://subdomain.trusted-domain.com",
        "https://not-trusted-domain.com",
        "null",
    ],
)
def test_cors_strictly_distinguishes_origins(client: TestClient, untrusted_origin: str):
    """Origins differing by port, protocol, subdomain, or prefix are NOT trusted."""
    response = client.get("/health", headers={"Origin": untrusted_origin})
    assert response.headers.get("access-control-allow-origin") is None


# ------------------------------------------------------------------------------
# C. Wildcard protection tests
# ------------------------------------------------------------------------------

def test_wildcard_rejected_by_parse_trusted_origins():
    """parse_trusted_origins must reject wildcard '*' rather than enabling unrestricted access."""
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        parse_trusted_origins("*")

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        parse_trusted_origins("http://localhost:5173, *")

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        parse_trusted_origins(" *, http://localhost:5173 ")

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        parse_trusted_origins(["*"])

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        parse_trusted_origins(["http://localhost:5173", "*"])


def test_wildcard_rejected_by_settings():
    """Settings must reject wildcard '*' in trusted_origins argument."""
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        Settings(trusted_origins="*")

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        Settings(trusted_origins=["*"])


def test_wildcard_rejected_by_environment_variable(monkeypatch):
    """Settings must reject wildcard '*' supplied via TRUSTED_ORIGINS environment variable."""
    monkeypatch.setenv("TRUSTED_ORIGINS", "*")
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        Settings()

    monkeypatch.setenv("TRUSTED_ORIGINS", "http://localhost:5173, *")
    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        Settings()


def test_create_app_rejects_wildcard():
    """create_app must fail clearly if wildcard origin is somehow configured with credentials."""
    mock_settings = Settings.__new__(Settings)
    mock_settings.app_env = "test"
    mock_settings.trusted_origins = ["*"]
    mock_settings.log_level = "INFO"

    with pytest.raises(ValueError, match=r"Wildcard origin '\*' is not allowed"):
        create_app(mock_settings)


def test_application_does_not_permit_wildcard_origins_in_default_app():
    """The default application instance must never combine wildcard origins with credentials."""
    app = create_app()
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            allow_origins = middleware.kwargs.get("allow_origins", [])
            assert "*" not in allow_origins
            assert allow_origins != ["*"]
            assert middleware.kwargs.get("allow_credentials") is True


# ------------------------------------------------------------------------------
# D. Configuration parsing tests
# ------------------------------------------------------------------------------

def test_parse_trusted_origins_comma_separated_and_whitespace():
    """Comma-separated origins must be trimmed and empty entries ignored."""
    raw = "  http://localhost:5173 , ,   , http://127.0.0.1:5173 ,  https://example.com  , "
    parsed = parse_trusted_origins(raw)
    assert parsed == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://example.com",
    ]


def test_parse_trusted_origins_empty_inputs():
    """Empty or whitespace-only inputs return an empty list without error."""
    assert parse_trusted_origins("") == []
    assert parse_trusted_origins("   ") == []
    assert parse_trusted_origins(",,,") == []


def test_parse_trusted_origins_trailing_slashes_normalized():
    """Trailing slashes on origins are stripped to ensure exact CORS matching."""
    parsed = parse_trusted_origins("http://localhost:5173/")
    assert parsed == ["http://localhost:5173"]


def test_local_development_defaults_when_env_not_set(monkeypatch):
    """When TRUSTED_ORIGINS is not set, local environment falls back to sensible local defaults."""
    monkeypatch.delenv("TRUSTED_ORIGINS", raising=False)
    settings = Settings(app_env="local")
    assert settings.trusted_origins == list(DEFAULT_LOCAL_ORIGINS)


def test_production_origins_environment_driven(monkeypatch):
    """Production environment requires origins to be supplied through server environment; no hardcoded prod domains."""
    monkeypatch.delenv("TRUSTED_ORIGINS", raising=False)
    prod_settings_no_env = Settings(app_env="production")
    # Without TRUSTED_ORIGINS, production has no trusted origins (secure by default)
    assert prod_settings_no_env.trusted_origins == []

    # When supplied via server environment
    monkeypatch.setenv("TRUSTED_ORIGINS", "https://app.campaignlift.com,https://admin.campaignlift.com")
    prod_settings_with_env = Settings(app_env="production")
    assert prod_settings_with_env.trusted_origins == [
        "https://app.campaignlift.com",
        "https://admin.campaignlift.com",
    ]


def test_env_var_overrides_local_defaults_without_merging(monkeypatch):
    """TRUSTED_ORIGINS environment variable overrides defaults completely without merging localhost."""
    monkeypatch.setenv("TRUSTED_ORIGINS", "https://some-explicit-origin.example")
    settings = Settings(app_env="local")
    # Must be ONLY that configured origin, not merged with localhost:5173
    assert settings.trusted_origins == ["https://some-explicit-origin.example"]


def test_multiple_origins_parsed_exactly(monkeypatch):
    """Multiple comma-separated origins are parsed to exactly those origins."""
    monkeypatch.setenv("TRUSTED_ORIGINS", "https://a.example, https://b.example")
    settings = Settings(app_env="local")
    assert settings.trusted_origins == ["https://a.example", "https://b.example"]

