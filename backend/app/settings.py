"""Application settings and environment configuration for CampaignLift backend.

Canonical planning sources:
- planning/architecture_plan.md
- planning/backend_plan.md
- backend/openapi.yaml
"""

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
