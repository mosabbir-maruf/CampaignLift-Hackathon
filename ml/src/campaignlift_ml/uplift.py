"""Uplift Modeling Algorithms module for CampaignLift.

Implements causal uplift modeling candidates:
- U0: Logistic Regression T-Learner (two models: treatment vs control)
- U1: LightGBM T-Learner (Step 14.2)
- B1: Logistic Regression S-Learner (Step 14.3)
- U2: LightGBM S-Learner (Step 14.3)

Strict Causal & Anti-Leakage Rules:
1. Potential outcomes are estimated from factual outcomes: y_transacted.
2. Ground truth 'true_uplift' is unobservable and must NEVER be used as a target or feature.
3. T-Learners fit separate estimators on treated (treatment == 1) and control (treatment == 0) cohorts.
4. S-Learners fit a single estimator with treatment included as a feature.
5. Uplift is calculated as counterfactual difference: uplift = p_treat - p_control.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    assert_no_forbidden_columns,
    load_train_val,
)


@dataclass
class UpliftPredictions:
    """Container for predicted counterfactual probabilities and individual treatment effect."""
    p_treat: np.ndarray
    p_control: np.ndarray
    uplift: np.ndarray

    def to_dataframe(self, index: Optional[pd.Index] = None) -> pd.DataFrame:
        """Convert predictions to a DataFrame with standard naming."""
        return pd.DataFrame(
            {
                "p_treat": self.p_treat,
                "p_control": self.p_control,
                "uplift": self.uplift,
            },
            index=index,
        )


@dataclass
class UpliftEvaluationResult:
    """Summary metrics of uplift predictions on a validation cohort."""
    candidate_id: str
    model_name: str
    mean_uplift: float
    mean_abs_uplift: float
    std_uplift: float
    min_uplift: float
    max_uplift: float
    p_treat_mean: float
    p_control_mean: float
    n_eval: int
    eval_type: str = "smoke"

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to serializable dictionary."""
        return {
            "candidate_id": self.candidate_id,
            "model_name": self.model_name,
            "eval_type": self.eval_type,
            "mean_uplift": round(self.mean_uplift, 5),
            "mean_abs_uplift": round(self.mean_abs_uplift, 5),
            "std_uplift": round(self.std_uplift, 5),
            "min_uplift": round(self.min_uplift, 5),
            "max_uplift": round(self.max_uplift, 5),
            "p_treat_mean": round(self.p_treat_mean, 5),
            "p_control_mean": round(self.p_control_mean, 5),
            "n_eval": self.n_eval,
        }


class LogisticTLearner:
    """Candidate U0: Two-model T-Learner using regularized Logistic Regression.

    Trains two independent estimators:
        - model_treat: fits P(Y=1 | X, T=1) on treated training customers
        - model_control: fits P(Y=1 | X, T=0) on control training customers

    Individual Treatment Effect (ITE / Uplift) is derived as:
        tau_hat(x) = p_treat(x) - p_control(x)
    """

    def __init__(
        self,
        random_state: int = 20261006,
        max_iter: int = 1000,
        c_penalty: float = 1.0,
    ) -> None:
        self.candidate_id = "U0"
        self.model_name = "logistic_t_learner"
        self.random_state = random_state
        self.max_iter = max_iter
        self.c_penalty = c_penalty
        self.categorical_cols = list(CATEGORICAL_COLUMNS)
        self.numeric_cols = list(NUMERIC_COLUMNS)
        self.feature_cols = list(FEATURE_COLUMNS)

        self.model_treat: Optional[Pipeline] = None
        self.model_control: Optional[Pipeline] = None
        self.is_fitted: bool = False
        self.n_train_treat: int = 0
        self.n_train_control: int = 0

    def _build_pipeline(self, seed_offset: int = 0) -> Pipeline:
        """Create a fresh preprocessing and logistic regression pipeline."""
        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    self.categorical_cols,
                ),
                (
                    "num",
                    StandardScaler(),
                    self.numeric_cols,
                ),
            ],
            remainder="drop",
        )

        classifier = LogisticRegression(
            C=self.c_penalty,
            max_iter=self.max_iter,
            random_state=self.random_state + seed_offset,
            solver="lbfgs",
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )

    def fit(self, train_df: pd.DataFrame) -> "LogisticTLearner":
        """Fit treated and control models on their respective training arms.

        Args:
            train_df: Training DataFrame containing features, treatment, and y_transacted.

        Returns:
            Fitted LogisticTLearner instance.

        Raises:
            ValueError: If required columns are missing, or an arm lacks sufficient rows.
            ForbiddenColumnError: If true_uplift or any latent column is present.
        """
        # Anti-leakage guard: assert no forbidden ground truth column in training
        assert_no_forbidden_columns(train_df)

        for col in [TARGET_COLUMN, TREATMENT_COLUMN]:
            if col not in train_df.columns:
                raise ValueError(f"Training DataFrame missing required column '{col}'")

        # Partition arms
        treat_mask = train_df[TREATMENT_COLUMN] == 1
        control_mask = train_df[TREATMENT_COLUMN] == 0

        treated_df = train_df[treat_mask]
        control_df = train_df[control_mask]

        if len(treated_df) == 0:
            raise ValueError("No treated rows (treatment == 1) found in training DataFrame")
        if len(control_df) == 0:
            raise ValueError("No control rows (treatment == 0) found in training DataFrame")

        self.n_train_treat = len(treated_df)
        self.n_train_control = len(control_df)

        X_treat = treated_df[self.feature_cols]
        y_treat = treated_df[TARGET_COLUMN].values

        X_control = control_df[self.feature_cols]
        y_control = control_df[TARGET_COLUMN].values

        # Build and fit treated estimator
        self.model_treat = self._build_pipeline(seed_offset=1)
        self.model_treat.fit(X_treat, y_treat)

        # Build and fit control estimator
        self.model_control = self._build_pipeline(seed_offset=2)
        self.model_control.fit(X_control, y_control)

        self.is_fitted = True
        return self

    def predict_uplift(self, df: pd.DataFrame) -> UpliftPredictions:
        """Predict counterfactual response probabilities and individual uplift.

        Args:
            df: DataFrame containing required feature columns.

        Returns:
            UpliftPredictions with p_treat, p_control, and uplift arrays.

        Raises:
            RuntimeError: If learner is not fitted yet.
        """
        if not self.is_fitted or self.model_treat is None or self.model_control is None:
            raise RuntimeError("Model is not fitted yet. Call fit() before predict_uplift().")

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        X = df[self.feature_cols]

        # Potential outcome under treatment P(Y=1 | X, T=1)
        p_treat = self.model_treat.predict_proba(X)[:, 1]

        # Potential outcome under control P(Y=1 | X, T=0)
        p_control = self.model_control.predict_proba(X)[:, 1]

        # Causal uplift tau = p_treat - p_control
        uplift = p_treat - p_control

        return UpliftPredictions(
            p_treat=p_treat,
            p_control=p_control,
            uplift=uplift,
        )

    def evaluate(self, val_df: pd.DataFrame, eval_type: str = "smoke") -> UpliftEvaluationResult:
        """Evaluate uplift candidate on validation split.

        Args:
            val_df: Validation DataFrame.
            eval_type: Evaluation identifier ('smoke', 'ml_dev', 'benchmark').

        Returns:
            UpliftEvaluationResult with summary statistics.
        """
        preds = self.predict_uplift(val_df)

        return UpliftEvaluationResult(
            candidate_id=self.candidate_id,
            model_name=self.model_name,
            mean_uplift=float(np.mean(preds.uplift)),
            mean_abs_uplift=float(np.mean(np.abs(preds.uplift))),
            std_uplift=float(np.std(preds.uplift)),
            min_uplift=float(np.min(preds.uplift)),
            max_uplift=float(np.max(preds.uplift)),
            p_treat_mean=float(np.mean(preds.p_treat)),
            p_control_mean=float(np.mean(preds.p_control)),
            n_eval=len(val_df),
            eval_type=eval_type,
        )

    def score_test(self, test_df: pd.DataFrame) -> UpliftEvaluationResult:
        """Score held-out test split once for final benchmark reporting.

        RESERVED: Call only after final model selection has occurred (Step 15.4).
        """
        return self.evaluate(test_df, eval_type="test_evaluation")


# -----------------------------------------------------------------------------
# Logistic S-Learner (Candidate B1)
# -----------------------------------------------------------------------------

class LogisticSLearner:
    """Candidate B1: Single-model S-Learner using regularized Logistic Regression.

    Trains a single estimator with the treatment indicator included as a feature:
        y ~ f(X, treatment)

    Counterfactual Individual Treatment Effect (ITE / Uplift) is derived as:
        tau_hat(x) = p(Y=1 | X=x, treatment=1) - p(Y=1 | X=x, treatment=0)
    """

    def __init__(
        self,
        random_state: int = 20261006,
        max_iter: int = 1000,
        c_penalty: float = 1.0,
    ) -> None:
        self.candidate_id = "B1"
        self.model_name = "logistic_s_learner"
        self.random_state = random_state
        self.max_iter = max_iter
        self.c_penalty = c_penalty
        self.categorical_cols = list(CATEGORICAL_COLUMNS)
        self.numeric_cols = list(NUMERIC_COLUMNS)
        self.feature_cols = list(FEATURE_COLUMNS)
        self.input_cols = self.feature_cols + [TREATMENT_COLUMN]

        self.model: Optional[Pipeline] = None
        self.is_fitted: bool = False
        self.n_train: int = 0

    def _build_pipeline(self) -> Pipeline:
        """Create preprocessing and logistic regression pipeline."""
        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    self.categorical_cols,
                ),
                (
                    "num",
                    StandardScaler(),
                    self.numeric_cols,
                ),
                (
                    "treatment",
                    "passthrough",
                    [TREATMENT_COLUMN],
                ),
            ],
            remainder="drop",
        )

        classifier = LogisticRegression(
            C=self.c_penalty,
            max_iter=self.max_iter,
            random_state=self.random_state,
            solver="lbfgs",
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )

    def fit(self, train_df: pd.DataFrame) -> "LogisticSLearner":
        """Fit single logistic regression estimator on all training data with treatment indicator."""
        assert_no_forbidden_columns(train_df)

        for col in [TARGET_COLUMN, TREATMENT_COLUMN]:
            if col not in train_df.columns:
                raise ValueError(f"Training DataFrame missing required column '{col}'")

        missing = [c for c in self.feature_cols if c not in train_df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        self.n_train = len(train_df)
        X = train_df[self.input_cols]
        y = train_df[TARGET_COLUMN].values

        self.model = self._build_pipeline()
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict_uplift(self, df: pd.DataFrame) -> UpliftPredictions:
        """Predict counterfactual response probabilities and individual uplift."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model is not fitted yet. Call fit() before predict_uplift().")

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        # Counterfactual: evaluate cohort with treatment = 1
        df_treat = df[self.feature_cols].copy()
        df_treat[TREATMENT_COLUMN] = 1
        p_treat = self.model.predict_proba(df_treat[self.input_cols])[:, 1]

        # Counterfactual: evaluate cohort with treatment = 0
        df_control = df[self.feature_cols].copy()
        df_control[TREATMENT_COLUMN] = 0
        p_control = self.model.predict_proba(df_control[self.input_cols])[:, 1]

        uplift = p_treat - p_control

        return UpliftPredictions(
            p_treat=p_treat,
            p_control=p_control,
            uplift=uplift,
        )

    def evaluate(self, val_df: pd.DataFrame, eval_type: str = "smoke") -> UpliftEvaluationResult:
        """Evaluate Logistic S-Learner candidate on validation split."""
        preds = self.predict_uplift(val_df)

        return UpliftEvaluationResult(
            candidate_id=self.candidate_id,
            model_name=self.model_name,
            mean_uplift=float(np.mean(preds.uplift)),
            mean_abs_uplift=float(np.mean(np.abs(preds.uplift))),
            std_uplift=float(np.std(preds.uplift)),
            min_uplift=float(np.min(preds.uplift)),
            max_uplift=float(np.max(preds.uplift)),
            p_treat_mean=float(np.mean(preds.p_treat)),
            p_control_mean=float(np.mean(preds.p_control)),
            n_eval=len(val_df),
            eval_type=eval_type,
        )

    def score_test(self, test_df: pd.DataFrame) -> UpliftEvaluationResult:
        """Score held-out test split once for final benchmark reporting (Step 15.4)."""
        return self.evaluate(test_df, eval_type="test_evaluation")


# -----------------------------------------------------------------------------
# LightGBM T-Learner (Candidate U1)
# -----------------------------------------------------------------------------

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
    LIGHTGBM_IMPORT_ERROR: Optional[str] = None
except Exception as _lgb_err:
    lgb = None  # type: ignore
    LIGHTGBM_AVAILABLE = False
    LIGHTGBM_IMPORT_ERROR = str(_lgb_err)


def load_train_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load hyperparameters from ml/config/train.yaml if present."""
    default_cfg: Dict[str, Any] = {
        "global_seed": 20261006,
        "lightgbm_t_learner": {
            "n_estimators": 100,
            "learning_rate": 0.05,
            "num_leaves": 15,
            "max_depth": 4,
            "min_child_samples": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "binary",
            "verbosity": -1,
        },
        "lightgbm_s_learner": {
            "n_estimators": 100,
            "learning_rate": 0.05,
            "num_leaves": 15,
            "max_depth": 4,
            "min_child_samples": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "binary",
            "verbosity": -1,
        },
    }

    if config_path:
        p = Path(config_path)
    else:
        # Default relative to this file
        p = Path(__file__).resolve().parents[2] / "config" / "train.yaml"

    if p.is_file():
        try:
            import yaml
            with p.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    return loaded
        except Exception:
            pass

    return default_cfg


class LightGBMTLearner:
    """Candidate U1: Two-model T-Learner using LightGBM Gradient Boosted Decision Trees.

    Fits two separate LightGBM binary classifiers:
        - model_treat: fits P(Y=1 | X, T=1) on treated cohort
        - model_control: fits P(Y=1 | X, T=0) on control cohort

    Categorical features are one-hot encoded; numeric features pass through on natural scale.
    """

    def __init__(
        self,
        random_state: int = 20261006,
        n_estimators: Optional[int] = None,
        learning_rate: Optional[float] = None,
        num_leaves: Optional[int] = None,
        max_depth: Optional[int] = None,
        min_child_samples: Optional[int] = None,
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                f"LightGBM is not available on this system ({LIGHTGBM_IMPORT_ERROR}). "
                "Per Step 14.2 instructions, keep LogisticTLearner as the validated fallback."
            )

        self.candidate_id = "U1"
        self.model_name = "lightgbm_t_learner"
        self.categorical_cols = list(CATEGORICAL_COLUMNS)
        self.numeric_cols = list(NUMERIC_COLUMNS)
        self.feature_cols = list(FEATURE_COLUMNS)

        # Load train.yaml defaults
        cfg = load_train_config(config_path)
        lgb_params = cfg.get("lightgbm_t_learner", {})

        self.random_state = random_state or cfg.get("global_seed", 20261006)
        self.n_estimators = n_estimators if n_estimators is not None else lgb_params.get("n_estimators", 100)
        self.learning_rate = learning_rate if learning_rate is not None else lgb_params.get("learning_rate", 0.05)
        self.num_leaves = num_leaves if num_leaves is not None else lgb_params.get("num_leaves", 15)
        self.max_depth = max_depth if max_depth is not None else lgb_params.get("max_depth", 4)
        self.min_child_samples = min_child_samples if min_child_samples is not None else lgb_params.get("min_child_samples", 5)

        self.model_treat: Optional[Pipeline] = None
        self.model_control: Optional[Pipeline] = None
        self.is_fitted: bool = False
        self.n_train_treat: int = 0
        self.n_train_control: int = 0

    def _build_pipeline(self, seed_offset: int = 0) -> Pipeline:
        """Create preprocessing and LightGBM pipeline."""
        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    self.categorical_cols,
                ),
            ],
            remainder="passthrough",  # Tree models operate on natural numerical scales
        )

        classifier = lgb.LGBMClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            min_child_samples=self.min_child_samples,
            random_state=self.random_state + seed_offset,
            objective="binary",
            verbosity=-1,
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )

    def fit(self, train_df: pd.DataFrame) -> "LightGBMTLearner":
        """Fit treated and control LightGBM models on their respective arms."""
        assert_no_forbidden_columns(train_df)

        for col in [TARGET_COLUMN, TREATMENT_COLUMN]:
            if col not in train_df.columns:
                raise ValueError(f"Training DataFrame missing required column '{col}'")

        treat_mask = train_df[TREATMENT_COLUMN] == 1
        control_mask = train_df[TREATMENT_COLUMN] == 0

        treated_df = train_df[treat_mask]
        control_df = train_df[control_mask]

        if len(treated_df) == 0:
            raise ValueError("No treated rows (treatment == 1) found in training DataFrame")
        if len(control_df) == 0:
            raise ValueError("No control rows (treatment == 0) found in training DataFrame")

        self.n_train_treat = len(treated_df)
        self.n_train_control = len(control_df)

        X_treat = treated_df[self.feature_cols]
        y_treat = treated_df[TARGET_COLUMN].values

        X_control = control_df[self.feature_cols]
        y_control = control_df[TARGET_COLUMN].values

        self.model_treat = self._build_pipeline(seed_offset=1)
        self.model_treat.fit(X_treat, y_treat)

        self.model_control = self._build_pipeline(seed_offset=2)
        self.model_control.fit(X_control, y_control)

        self.is_fitted = True
        return self

    def predict_uplift(self, df: pd.DataFrame) -> UpliftPredictions:
        """Predict counterfactual response probabilities and individual uplift via LightGBM."""
        if not self.is_fitted or self.model_treat is None or self.model_control is None:
            raise RuntimeError("Model is not fitted yet. Call fit() before predict_uplift().")

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        X = df[self.feature_cols]

        p_treat = self.model_treat.predict_proba(X)[:, 1]
        p_control = self.model_control.predict_proba(X)[:, 1]
        uplift = p_treat - p_control

        return UpliftPredictions(
            p_treat=p_treat,
            p_control=p_control,
            uplift=uplift,
        )

    def evaluate(self, val_df: pd.DataFrame, eval_type: str = "smoke") -> UpliftEvaluationResult:
        """Evaluate LightGBM T-Learner on validation split."""
        preds = self.predict_uplift(val_df)

        return UpliftEvaluationResult(
            candidate_id=self.candidate_id,
            model_name=self.model_name,
            mean_uplift=float(np.mean(preds.uplift)),
            mean_abs_uplift=float(np.mean(np.abs(preds.uplift))),
            std_uplift=float(np.std(preds.uplift)),
            min_uplift=float(np.min(preds.uplift)),
            max_uplift=float(np.max(preds.uplift)),
            p_treat_mean=float(np.mean(preds.p_treat)),
            p_control_mean=float(np.mean(preds.p_control)),
            n_eval=len(val_df),
            eval_type=eval_type,
        )

    def score_test(self, test_df: pd.DataFrame) -> UpliftEvaluationResult:
        """Score held-out test split once for final benchmark reporting (Step 15.4)."""
        return self.evaluate(test_df, eval_type="test_evaluation")


# -----------------------------------------------------------------------------
# LightGBM S-Learner (Candidate U2)
# -----------------------------------------------------------------------------

class LightGBMSLearner:
    """Candidate U2: Single-model S-Learner using LightGBM Gradient Boosted Decision Trees.

    Trains a single LightGBM binary classifier with treatment indicator as a feature:
        y ~ f(X, treatment)

    Counterfactual Individual Treatment Effect (ITE / Uplift) is derived as:
        tau_hat(x) = p(Y=1 | X=x, treatment=1) - p(Y=1 | X=x, treatment=0)
    """

    def __init__(
        self,
        random_state: int = 20261006,
        n_estimators: Optional[int] = None,
        learning_rate: Optional[float] = None,
        num_leaves: Optional[int] = None,
        max_depth: Optional[int] = None,
        min_child_samples: Optional[int] = None,
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        if not LIGHTGBM_AVAILABLE:
            raise ImportError(
                f"LightGBM is not available on this system ({LIGHTGBM_IMPORT_ERROR}). "
                "Per Step 14.3 instructions, keep LogisticSLearner as the validated fallback."
            )

        self.candidate_id = "U2"
        self.model_name = "lightgbm_s_learner"
        self.categorical_cols = list(CATEGORICAL_COLUMNS)
        self.numeric_cols = list(NUMERIC_COLUMNS)
        self.feature_cols = list(FEATURE_COLUMNS)
        self.input_cols = self.feature_cols + [TREATMENT_COLUMN]

        # Load train.yaml defaults
        cfg = load_train_config(config_path)
        lgb_params = cfg.get("lightgbm_s_learner", cfg.get("lightgbm_t_learner", {}))

        self.random_state = random_state or cfg.get("global_seed", 20261006)
        self.n_estimators = n_estimators if n_estimators is not None else lgb_params.get("n_estimators", 100)
        self.learning_rate = learning_rate if learning_rate is not None else lgb_params.get("learning_rate", 0.05)
        self.num_leaves = num_leaves if num_leaves is not None else lgb_params.get("num_leaves", 15)
        self.max_depth = max_depth if max_depth is not None else lgb_params.get("max_depth", 4)
        self.min_child_samples = min_child_samples if min_child_samples is not None else lgb_params.get("min_child_samples", 5)

        self.model: Optional[Pipeline] = None
        self.is_fitted: bool = False
        self.n_train: int = 0

    def _build_pipeline(self) -> Pipeline:
        """Create preprocessing and LightGBM pipeline."""
        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    self.categorical_cols,
                ),
            ],
            remainder="passthrough",  # Numeric features and treatment pass through
        )

        classifier = lgb.LGBMClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            min_child_samples=self.min_child_samples,
            random_state=self.random_state,
            objective="binary",
            verbosity=-1,
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )

    def fit(self, train_df: pd.DataFrame) -> "LightGBMSLearner":
        """Fit single LightGBM binary classifier on all training data with treatment indicator."""
        assert_no_forbidden_columns(train_df)

        for col in [TARGET_COLUMN, TREATMENT_COLUMN]:
            if col not in train_df.columns:
                raise ValueError(f"Training DataFrame missing required column '{col}'")

        missing = [c for c in self.feature_cols if c not in train_df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        self.n_train = len(train_df)
        X = train_df[self.input_cols]
        y = train_df[TARGET_COLUMN].values

        self.model = self._build_pipeline()
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict_uplift(self, df: pd.DataFrame) -> UpliftPredictions:
        """Predict counterfactual response probabilities and individual uplift via LightGBM."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model is not fitted yet. Call fit() before predict_uplift().")

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame missing required feature columns: {missing}")

        # Counterfactual: evaluate cohort with treatment = 1
        df_treat = df[self.feature_cols].copy()
        df_treat[TREATMENT_COLUMN] = 1
        p_treat = self.model.predict_proba(df_treat[self.input_cols])[:, 1]

        # Counterfactual: evaluate cohort with treatment = 0
        df_control = df[self.feature_cols].copy()
        df_control[TREATMENT_COLUMN] = 0
        p_control = self.model.predict_proba(df_control[self.input_cols])[:, 1]

        uplift = p_treat - p_control

        return UpliftPredictions(
            p_treat=p_treat,
            p_control=p_control,
            uplift=uplift,
        )

    def evaluate(self, val_df: pd.DataFrame, eval_type: str = "smoke") -> UpliftEvaluationResult:
        """Evaluate LightGBM S-Learner on validation split."""
        preds = self.predict_uplift(val_df)

        return UpliftEvaluationResult(
            candidate_id=self.candidate_id,
            model_name=self.model_name,
            mean_uplift=float(np.mean(preds.uplift)),
            mean_abs_uplift=float(np.mean(np.abs(preds.uplift))),
            std_uplift=float(np.std(preds.uplift)),
            min_uplift=float(np.min(preds.uplift)),
            max_uplift=float(np.max(preds.uplift)),
            p_treat_mean=float(np.mean(preds.p_treat)),
            p_control_mean=float(np.mean(preds.p_control)),
            n_eval=len(val_df),
            eval_type=eval_type,
        )

    def score_test(self, test_df: pd.DataFrame) -> UpliftEvaluationResult:
        """Score held-out test split once for final benchmark reporting (Step 15.4)."""
        return self.evaluate(test_df, eval_type="test_evaluation")


# -----------------------------------------------------------------------------
# Convenience Functions & Runners
# -----------------------------------------------------------------------------

def train_logistic_t_learner(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
) -> LogisticTLearner:
    """Convenience helper to instantiate and fit a LogisticTLearner."""
    learner = LogisticTLearner(random_state=random_state)
    learner.fit(train_df)
    return learner


def train_logistic_s_learner(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
) -> LogisticSLearner:
    """Convenience helper to instantiate and fit a LogisticSLearner."""
    learner = LogisticSLearner(random_state=random_state)
    learner.fit(train_df)
    return learner


def train_lightgbm_t_learner(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
    config_path: Optional[Union[str, Path]] = None,
) -> LightGBMTLearner:
    """Convenience helper to instantiate and fit a LightGBMTLearner."""
    learner = LightGBMTLearner(random_state=random_state, config_path=config_path)
    learner.fit(train_df)
    return learner


def train_lightgbm_s_learner(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
    config_path: Optional[Union[str, Path]] = None,
) -> LightGBMSLearner:
    """Convenience helper to instantiate and fit a LightGBMSLearner."""
    learner = LightGBMSLearner(random_state=random_state, config_path=config_path)
    learner.fit(train_df)
    return learner


def run_smoke_logistic_t_learner(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
) -> Dict[str, Any]:
    """Execute smoke validation run for Logistic T-Learner on fixture/dev data."""
    train_df, val_df = load_train_val(dataset_dir)
    learner = train_logistic_t_learner(train_df)
    eval_result = learner.evaluate(val_df, eval_type="smoke")
    return eval_result.to_dict()


def run_smoke_logistic_s_learner(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
) -> Dict[str, Any]:
    """Execute smoke validation run for Logistic S-Learner on fixture/dev data."""
    train_df, val_df = load_train_val(dataset_dir)
    learner = train_logistic_s_learner(train_df)
    eval_result = learner.evaluate(val_df, eval_type="smoke")
    return eval_result.to_dict()


def run_smoke_lightgbm_t_learner(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    output_metrics_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute smoke validation run for LightGBM T-Learner on fixture/dev data.

    Returns:
        Metrics dictionary or failure notification if LightGBM is unavailable.
    """
    if not LIGHTGBM_AVAILABLE:
        result = {
            "candidate_id": "U1",
            "model_name": "lightgbm_t_learner",
            "status": "import_failed",
            "error": LIGHTGBM_IMPORT_ERROR,
            "fallback": "logistic_t_learner",
        }
    else:
        train_df, val_df = load_train_val(dataset_dir)
        learner = train_lightgbm_t_learner(train_df)
        eval_result = learner.evaluate(val_df, eval_type="smoke")
        result = eval_result.to_dict()

    if output_metrics_path:
        out_p = Path(output_metrics_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def run_smoke_lightgbm_s_learner(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    output_metrics_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute smoke validation run for LightGBM S-Learner on fixture/dev data.

    Returns:
        Metrics dictionary or failure notification if LightGBM is unavailable.
    """
    if not LIGHTGBM_AVAILABLE:
        result = {
            "candidate_id": "U2",
            "model_name": "lightgbm_s_learner",
            "status": "import_failed",
            "error": LIGHTGBM_IMPORT_ERROR,
            "fallback": "logistic_s_learner",
        }
    else:
        train_df, val_df = load_train_val(dataset_dir)
        learner = train_lightgbm_s_learner(train_df)
        eval_result = learner.evaluate(val_df, eval_type="smoke")
        result = eval_result.to_dict()

    if output_metrics_path:
        out_p = Path(output_metrics_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    print("Logistic T-Learner (U0) Smoke Metrics:")
    print(json.dumps(run_smoke_logistic_t_learner(), indent=2))
    print("\nLogistic S-Learner (B1) Smoke Metrics:")
    print(json.dumps(run_smoke_logistic_s_learner(), indent=2))
    print("\nLightGBM T-Learner (U1) Smoke Metrics:")
    print(json.dumps(run_smoke_lightgbm_t_learner(), indent=2))
    print("\nLightGBM S-Learner (U2) Smoke Metrics:")
    print(json.dumps(run_smoke_lightgbm_s_learner(), indent=2))

