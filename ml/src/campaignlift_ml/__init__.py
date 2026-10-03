"""CampaignLift Machine Learning Package.

Provides uplift modeling candidates (T-learner, S-learner), anti-leakage data loading,
evaluation metrics (Qini curve, AUUC), and model serialization for production inference.
"""

from .data import (
    DatasetSplits,
    ForbiddenColumnError,
    ChecksumMismatchError,
    ManifestError,
    load_manifest,
    load_dataset_splits,
    load_train_val,
    assert_no_forbidden_columns,
    compute_sha256,
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    IDENTIFIER_COLUMNS,
)

from .baseline import (
    ResponseBaselineModel,
    BaselineEvaluationResult,
    train_response_baseline,
    run_smoke_baseline,
)

__all__ = [
    "DatasetSplits",
    "ForbiddenColumnError",
    "ChecksumMismatchError",
    "ManifestError",
    "load_manifest",
    "load_dataset_splits",
    "load_train_val",
    "assert_no_forbidden_columns",
    "compute_sha256",
    "CATEGORICAL_COLUMNS",
    "NUMERIC_COLUMNS",
    "FEATURE_COLUMNS",
    "TARGET_COLUMN",
    "TREATMENT_COLUMN",
    "IDENTIFIER_COLUMNS",
    "ResponseBaselineModel",
    "BaselineEvaluationResult",
    "train_response_baseline",
    "run_smoke_baseline",
]
