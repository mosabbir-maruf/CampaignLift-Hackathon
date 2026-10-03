"""Uplift Modeling Algorithms module for CampaignLift.

Implements causal uplift modeling candidates:
- U0: Logistic Regression T-Learner (two models: treatment vs control)
- U1: LightGBM T-Learner (Step 14.2)
- U2: LightGBM S-Learner (Step 14.3)

Strict Causal & Anti-Leakage Rules:
1. Potential outcomes are estimated from factual outcomes: y_transacted.
2. Ground truth 'true_uplift' is unobservable and must NEVER be used as a target or feature.
3. T-Learner fits separate estimators on treated (treatment == 1) and control (treatment == 0) cohorts.
4. Uplift is calculated as: uplift = p_treat - p_control.
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


def train_logistic_t_learner(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
) -> LogisticTLearner:
    """Convenience helper to instantiate and fit a LogisticTLearner.

    Args:
        train_df: Training DataFrame.
        random_state: Reproducibility seed.

    Returns:
        Fitted LogisticTLearner instance.
    """
    learner = LogisticTLearner(random_state=random_state)
    learner.fit(train_df)
    return learner


def run_smoke_logistic_t_learner(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
) -> Dict[str, Any]:
    """Execute smoke validation run for Logistic T-Learner on fixture/dev data.

    Args:
        dataset_dir: Directory containing features and splits (default: fixture_v1).

    Returns:
        Metrics dictionary marked as 'smoke'.
    """
    train_df, val_df = load_train_val(dataset_dir)
    learner = train_logistic_t_learner(train_df)
    eval_result = learner.evaluate(val_df, eval_type="smoke")
    return eval_result.to_dict()


if __name__ == "__main__":
    metrics = run_smoke_logistic_t_learner()
    print("Logistic T-Learner Smoke Metrics:")
    print(json.dumps(metrics, indent=2))
