"""Inference module re-export for CampaignLift backend."""

from backend.app.services.inference import (
    CAMPAIGN_FIELDS,
    FORBIDDEN_COLUMNS,
    FeatureMismatchError,
    FeatureTableNotReadyError,
    ForbiddenColumnError,
    ModelNotReadyError,
    assert_no_forbidden_columns,
    compute_uplift_deciles,
    ensure_db_schema,
    load_feature_table,
    load_model_artifact,
    score_campaign_population,
)

__all__ = [
    "FORBIDDEN_COLUMNS",
    "CAMPAIGN_FIELDS",
    "ForbiddenColumnError",
    "FeatureMismatchError",
    "ModelNotReadyError",
    "FeatureTableNotReadyError",
    "assert_no_forbidden_columns",
    "ensure_db_schema",
    "load_model_artifact",
    "load_feature_table",
    "compute_uplift_deciles",
    "score_campaign_population",
]
