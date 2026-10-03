"""Top-level experiment package re-export for CampaignLift backend.

Canonical planning sources:
- planning/backend_plan.md
- tasks/assaduzzaman/20_experiment_intelligence_api.md
"""

from backend.app.services.experiment import (
    CANONICAL_SLICE_DIMENSIONS,
    MIN_SUPPORT_DEFAULT,
    ExperimentDataNotReadyError,
    ForbiddenColumnError,
    compute_experiment_summary,
    derive_activity_band,
    derive_exposure_band,
    ensure_experiment_db_schema,
    get_or_create_experiment_summary,
)

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
