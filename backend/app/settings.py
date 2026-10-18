"""Application settings and environment configuration for CampaignLift backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Repository root is 3 levels up from backend/app/settings.py
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Optionally load .env from repository root if present (gitignored, safe fallback)
load_dotenv(REPO_ROOT / ".env")


def resolve_path(raw_path: str | Path, base_dir: Path = REPO_ROOT) -> Path:
    """Resolve a relative path against the repository root, preserving absolute paths."""
    p = Path(raw_path)
    if not p.is_absolute():
        p = base_dir / p
    return p


DEFAULT_LOCAL_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def parse_trusted_origins(
    raw_origins: str | list[str] | tuple[str, ...] | None = None,
    app_env: str = "local",
    allow_credentials: bool = True,
) -> list[str]:
    """Parse comma-separated origin string or iterable into clean trusted origins.

    Trims whitespace, ignores empty entries, and strictly rejects wildcard '*'
    when credentials are enabled. Sensible local development defaults are only
    applied in local/dev/test environments when no explicit origins are supplied.
    """
    if raw_origins is None:
        raw_env = os.getenv("TRUSTED_ORIGINS")
        if raw_env is not None:
            raw_origins = raw_env
        elif app_env in ("local", "dev", "development", "test"):
            return list(DEFAULT_LOCAL_ORIGINS)
        else:
            return []

    if isinstance(raw_origins, (list, tuple, set)):
        items = [str(x) for x in raw_origins]
    else:
        items = str(raw_origins).split(",")

    cleaned: list[str] = []
    for item in items:
        origin = item.strip()
        if not origin:
            continue
        if origin == "*":
            if allow_credentials:
                raise ValueError(
                    "Wildcard origin '*' is not allowed when allow_credentials=True. "
                    "Specify explicit trusted origins."
                )
            raise ValueError(
                "Wildcard origin '*' is not permitted in trusted origins configuration."
            )
        if origin.endswith("/") and not origin.endswith("://"):
            origin = origin.rstrip("/")
        cleaned.append(origin)

    return cleaned


@dataclass
class Settings:
    """Backend application configuration loaded from environment variables."""

    app_env: str = field(
        default_factory=lambda: os.getenv("APP_ENV", "local")
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./campaignlift.db")
    )
    model_artifact_dir: str = field(
        default_factory=lambda: os.getenv(
            "MODEL_ARTIFACT_DIR",
            "artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        )
    )
    dataset_version: str = field(
        default_factory=lambda: os.getenv(
            "DATASET_VERSION",
            "cl-synth-ml_dev-20261006-8ad556a",
        )
    )
    feature_table_path: str = field(
        default_factory=lambda: os.getenv(
            "FEATURE_TABLE_PATH",
            "data/fixtures/fixture_v1/features.json",
        )
    )
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "") or None
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    session_secret: Optional[str] = None
    manager_password: Optional[str] = None
    viewer_password: Optional[str] = None
    auth_required: bool = False
    trusted_origins: list[str] = field(default=None)  # type: ignore[arg-type,assignment]

    def __post_init__(self) -> None:
        """Validate and normalize settings fields."""
        self.trusted_origins = parse_trusted_origins(
            self.trusted_origins, app_env=self.app_env
        )
        if self.app_env != "test":
            if self.session_secret is None:
                self.session_secret = os.getenv("SESSION_SECRET") or None
            if self.manager_password is None:
                self.manager_password = os.getenv("MANAGER_PASSWORD") or None
            if self.viewer_password is None:
                self.viewer_password = os.getenv("VIEWER_PASSWORD") or None
            if not self.auth_required:
                self.auth_required = os.getenv("AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")

    @property
    def resolved_model_artifact_dir(self) -> Path:
        """Absolute path to the model artifact directory."""
        return resolve_path(self.model_artifact_dir)

    @property
    def resolved_feature_table_path(self) -> Path:
        """Absolute path to the customer feature table file."""
        return resolve_path(self.feature_table_path)


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global Settings instance, instantiating it if not yet loaded."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
