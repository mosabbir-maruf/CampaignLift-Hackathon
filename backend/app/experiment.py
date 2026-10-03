"""Top-level experiment package re-export for CampaignLift backend."""

from backend.app.services.experiment import (
    CANONICAL_SLICE_DIMENSIONS,
    MIN_SUPPORT_DEFAULT,
    ExperimentDataNotReadyError,
    compute_experiment_summary,
    derive_activity_band,
    derive_exposure_band,
    ensure_experiment_db_schema,
    get_or_create_experiment_summary,
)
from backend.app.services.inference import ForbiddenColumnError

__all__ = [
    "CANONICAL_SLICE_DIMENSIONS",
    "MIN_SUPPORT_DEFAULT",
    "ExperimentDataNotReadyError",
    "ForbiddenColumnError",
    "compute_experiment_summary",
    "derive_activity_band",
    "derive_exposure_band",
    "ensure_experiment_db_schema",
    "get_or_create_experiment_summary",
]
