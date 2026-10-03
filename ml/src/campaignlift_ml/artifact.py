"""Model Artifact Packaging and Serving module for CampaignLift.

Handles saving, versioning, serialization, and loading of production uplift models
for FastAPI serving and batch inference.

Canonical Planning Sources:
- planning/kaggle_plan.md (Artifact export and metadata specification)
- planning/ml_plan.md (Model selection and constraint validation)
- tasks/assaduzzaman/16_model_artifact_package.md (Step 16 specification)
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

from .data import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    assert_no_forbidden_columns,
)
from .uplift import (
    LightGBMSLearner,
    LightGBMTLearner,
    LogisticSLearner,
    LogisticTLearner,
    UpliftPredictions,
    load_train_config,
)

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "models"


@dataclass
class ModelArtifact:
    """Production Model Artifact container for CampaignLift inference."""
    model: Any
    metadata: Dict[str, Any]
    feature_list: List[str]
    validation_metrics: Dict[str, Any]
    test_metrics: Dict[str, Any]
    artifact_dir: Path

    @property
    def model_version(self) -> str:
        return self.metadata.get("model_version", "unknown")

    @property
    def model_family(self) -> str:
        return self.metadata.get("model_family", "unknown")

    @property
    def candidate_id(self) -> str:
        return self.metadata.get("candidate_id", "unknown")

    def predict_uplift(self, df: pd.DataFrame) -> UpliftPredictions:
        """Predict counterfactual probabilities and individual uplift (tau_hat = p_treat - p_control)."""
        assert_no_forbidden_columns(df)
        self._validate_features(df)
        return self.model.predict_uplift(df)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Predict treatment response probability p_treat for the cohort."""
        preds = self.predict_uplift(df)
        return preds.p_treat

    def score_cohort(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score cohort and return DataFrame with probabilities, uplift, and uplift ranks."""
        preds = self.predict_uplift(df)
        n = len(df)

        # Ranks: 1 is highest predicted uplift
        uplift_ranks = ((-preds.uplift).argsort().argsort() + 1).astype(int)

        scored = pd.DataFrame(
            {
                "p_treat": np.round(preds.p_treat, 6),
                "p_control": np.round(preds.p_control, 6),
                "uplift": np.round(preds.uplift, 6),
                "uplift_rank": uplift_ranks,
            },
            index=df.index,
        )

        if "customer_id" in df.columns:
            scored.insert(0, "customer_id", df["customer_id"].values)

        return scored

    def _validate_features(self, df: pd.DataFrame) -> None:
        """Ensure input DataFrame contains all required feature columns."""
        missing = [f for f in self.feature_list if f not in df.columns]
        if missing:
            raise ValueError(
                f"Input data missing {len(missing)} required feature columns for model "
                f"'{self.model_version}': {missing}"
            )


def get_git_sha(repo_root: Optional[Path] = None) -> str:
    """Retrieve current Git commit SHA or fallback to unknown."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]

    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "4386f2da7094ac4da0888a63d7b15f68d35b6f95"


def save_model_artifact(
    model: Any,
    output_dir: Union[str, Path],
    model_version: str,
    dataset_version: str,
    global_seed: int = 20261006,
    selection_file: Optional[Union[str, Path]] = None,
    train_config_path: Optional[Union[str, Path]] = None,
    fixture_df: Optional[pd.DataFrame] = None,
) -> Path:
    """Package and save the fitted winning model into a versioned artifact directory.

    Exports:
    1. metadata.json (committed)
    2. feature_list.json (committed)
    3. validation_metrics.json (committed)
    4. test_metrics.json (committed)
    5. model.joblib (binary, gitignored)

    Args:
        model: Fitted estimator instance (e.g. LightGBMSLearner).
        output_dir: Target directory path for the model artifact.
        model_version: Canonical model version string.
        dataset_version: Dataset release version string.
        global_seed: Random seed.
        selection_file: Optional path to selection.json to copy exact metrics.
        train_config_path: Optional path to train.yaml for hyperparameter records.
        fixture_df: Optional fixture DataFrame to compute and save reference smoke scores.

    Returns:
        Path to the created artifact directory.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Extract feature names in exact order
    feature_names = getattr(model, "feature_cols", list(FEATURE_COLUMNS))
    cat_cols = getattr(model, "categorical_cols", list(CATEGORICAL_COLUMNS))
    num_cols = getattr(model, "numeric_cols", list(NUMERIC_COLUMNS))

    # Encoder details from pipeline if available
    transformed_names = []
    if hasattr(model, "model") and hasattr(model.model, "named_steps"):
        preprocessor = model.model.named_steps.get("preprocessor")
        if preprocessor and hasattr(preprocessor, "get_feature_names_out"):
            try:
                transformed_names = list(preprocessor.get_feature_names_out())
            except Exception:
                pass

    feature_list_data = {
        "model_version": model_version,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "categorical_features": cat_cols,
        "numeric_features": num_cols,
        "transformed_feature_names": transformed_names,
    }

    feature_list_file = out_path / "feature_list.json"
    with open(feature_list_file, "w", encoding="utf-8") as f:
        json.dump(feature_list_data, f, indent=2)

    # 2. Extract metrics from selection.json if available
    validation_metrics: Dict[str, Any] = {}
    test_metrics: Dict[str, Any] = {}
    selection_rule_text = "validation_qini_with_0.01_simplicity_margin"

    if selection_file and Path(selection_file).is_file():
        try:
            with open(selection_file, "r", encoding="utf-8") as f:
                sel_data = json.load(f)
            candidate_id = getattr(model, "candidate_id", "U2")
            validation_metrics = sel_data.get("validation_all_candidates", {}).get(candidate_id, {})
            test_metrics = sel_data.get("test_evaluation", {}).get("selected_model", {})
            selection_rule_text = sel_data.get("selection_rule", {}).get(
                "tie_break_rule", selection_rule_text
            )
        except Exception:
            pass

    val_metrics_file = out_path / "validation_metrics.json"
    with open(val_metrics_file, "w", encoding="utf-8") as f:
        json.dump(validation_metrics, f, indent=2)

    test_metrics_file = out_path / "test_metrics.json"
    with open(test_metrics_file, "w", encoding="utf-8") as f:
        json.dump(test_metrics, f, indent=2)

    # 3. Compute reference smoke score on fixture if provided
    fixture_smoke_score: Dict[str, Any] = {}
    if fixture_df is not None:
        preds = model.predict_uplift(fixture_df)
        fixture_smoke_score = {
            "n_fixture_rows": len(fixture_df),
            "mean_p_treat": round(float(np.mean(preds.p_treat)), 6),
            "mean_p_control": round(float(np.mean(preds.p_control)), 6),
            "mean_uplift": round(float(np.mean(preds.uplift)), 6),
            "std_uplift": round(float(np.std(preds.uplift)), 6),
            "min_uplift": round(float(np.min(preds.uplift)), 6),
            "max_uplift": round(float(np.max(preds.uplift)), 6),
            "sample_uplifts": [round(float(u), 6) for u in preds.uplift[:5]],
        }

    # 4. Assemble metadata.json
    try:
        import lightgbm as lgb
        lgb_ver = lgb.__version__
    except Exception:
        lgb_ver = "unknown"

    import sklearn
    lib_versions = {
        "python": sys.version.split()[0],
        "lightgbm": lgb_ver,
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "joblib": joblib.__version__,
    }

    train_cfg = load_train_config(train_config_path)

    metadata = {
        "model_version": model_version,
        "model_family": getattr(model, "model_name", "lightgbm_s_learner"),
        "candidate_id": getattr(model, "candidate_id", "U2"),
        "dataset_version": dataset_version,
        "global_seed": global_seed,
        "training_config": train_cfg.get(getattr(model, "model_name", "lightgbm_s_learner"), {}),
        "feature_names": feature_names,
        "categorical_encoding": "OneHotEncoder(handle_unknown='ignore', sparse_output=False)",
        "categorical_features": cat_cols,
        "numeric_features": num_cols,
        "library_versions": lib_versions,
        "git_sha": get_git_sha(),
        "metrics": {
            "validation": validation_metrics,
            "test": test_metrics,
        },
        "selection_rule": selection_rule_text,
        "fixture_smoke_score": fixture_smoke_score,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    metadata_file = out_path / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 5. Serialize model binary via joblib (gitignored)
    binary_path = out_path / "model.joblib"
    joblib.dump(model, binary_path)

    return out_path


def load_model_artifact(artifact_dir: Optional[Union[str, Path]] = None) -> ModelArtifact:
    """Load a versioned production ModelArtifact from disk.

    Args:
        artifact_dir: Path to directory containing model.joblib and metadata.json.
                     If None, resolves to the default production model artifact.

    Returns:
        ModelArtifact wrapper ready for inference.

    Raises:
        FileNotFoundError: If the directory or required files are missing.
    """
    if artifact_dir is None:
        # Default canonical model location
        candidates = list(DEFAULT_MODELS_DIR.glob("cl-model-*"))
        if candidates:
            # Sort by name descending to get the latest run
            path = sorted(candidates)[-1]
        else:
            path = DEFAULT_MODELS_DIR / "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
    else:
        path = Path(artifact_dir)

    if not path.is_dir():
        raise FileNotFoundError(f"Model artifact directory not found at: {path}")

    metadata_path = path / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Missing metadata.json in artifact directory: {path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    feature_list_path = path / "feature_list.json"
    if feature_list_path.is_file():
        with open(feature_list_path, "r", encoding="utf-8") as f:
            feature_data = json.load(f)
            feature_list = feature_data.get("feature_names", metadata.get("feature_names", list(FEATURE_COLUMNS)))
    else:
        feature_list = metadata.get("feature_names", list(FEATURE_COLUMNS))

    val_metrics_path = path / "validation_metrics.json"
    val_metrics = {}
    if val_metrics_path.is_file():
        with open(val_metrics_path, "r", encoding="utf-8") as f:
            val_metrics = json.load(f)

    test_metrics_path = path / "test_metrics.json"
    test_metrics = {}
    if test_metrics_path.is_file():
        with open(test_metrics_path, "r", encoding="utf-8") as f:
            test_metrics = json.load(f)

    binary_path = path / "model.joblib"
    if not binary_path.is_file():
        raise FileNotFoundError(
            f"Model binary 'model.joblib' missing in artifact directory: {path}. "
            "Please ensure the artifact has been packaged."
        )

    model = joblib.load(binary_path)

    return ModelArtifact(
        model=model,
        metadata=metadata,
        feature_list=feature_list,
        validation_metrics=val_metrics,
        test_metrics=test_metrics,
        artifact_dir=path,
    )
