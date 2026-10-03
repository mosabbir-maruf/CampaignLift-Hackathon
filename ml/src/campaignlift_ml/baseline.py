"""Response Baseline Model (Candidate B0) for CampaignLift.

Implements the traditional marketing question:
    "If we offer, how likely is a customer to transact?" -> p_treat

Fits a Logistic Regression model on treated rows (treatment == 1) of the training split only.
Categorical features are one-hot encoded and numerical features are standardized using parameters
fit strictly on the training partition.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    load_train_val,
)


@dataclass
class BaselineEvaluationResult:
    """Evaluation summary metrics for the response baseline model."""
    auc: Optional[float]
    brier_score: float
    mean_p_treat: float
    min_p_treat: float
    max_p_treat: float
    n_eval_total: int
    n_eval_treated: int
    eval_type: str = "smoke"
    model_name: str = "logistic_regression_b0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to serializable dictionary."""
        return {
            "model_name": self.model_name,
            "eval_type": self.eval_type,
            "auc": round(self.auc, 4) if self.auc is not None else None,
            "brier_score": round(self.brier_score, 4),
            "mean_p_treat": round(self.mean_p_treat, 4),
            "min_p_treat": round(self.min_p_treat, 4),
            "max_p_treat": round(self.max_p_treat, 4),
            "n_eval_total": self.n_eval_total,
            "n_eval_treated": self.n_eval_treated,
        }


class ResponseBaselineModel:
    """Logistic Regression response baseline (B0) trained on treated cohort."""

    def __init__(
        self,
        random_state: int = 20261006,
        max_iter: int = 1000,
        c_penalty: float = 1.0,
    ) -> None:
        self.random_state = random_state
        self.max_iter = max_iter
        self.c_penalty = c_penalty
        self.categorical_cols = list(CATEGORICAL_COLUMNS)
        self.numeric_cols = list(NUMERIC_COLUMNS)
        self.feature_cols = list(FEATURE_COLUMNS)
        self.pipeline: Optional[Pipeline] = None
        self.is_fitted: bool = False
        self.n_treated_train: int = 0

    def fit(self, train_df: pd.DataFrame) -> "ResponseBaselineModel":
        """Fit baseline logistic regression strictly on treated training rows.

        Args:
            train_df: Training DataFrame containing features, treatment, and y_transacted.

        Returns:
            Fitted ResponseBaselineModel instance.

        Raises:
            ValueError: If required columns are missing or no treated rows exist.
        """
        for col in [TARGET_COLUMN, TREATMENT_COLUMN]:
            if col not in train_df.columns:
                raise ValueError(f"Training DataFrame missing required column '{col}'")

        # 1. Strictly filter to treated rows only (T == 1)
        treated_mask = train_df[TREATMENT_COLUMN] == 1
        treated_df = train_df[treated_mask]

        if len(treated_df) == 0:
            raise ValueError("No treated rows (treatment == 1) found in training DataFrame")

        self.n_treated_train = len(treated_df)

        X_treated = treated_df[self.feature_cols]
        y_treated = treated_df[TARGET_COLUMN].values

        # 2. Build preprocessor (OneHotEncoder for categorical, StandardScaler for numeric)
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

        # 3. Assemble and fit pipeline
        classifier = LogisticRegression(
            C=self.c_penalty,
            max_iter=self.max_iter,
            random_state=self.random_state,
            solver="lbfgs",
        )

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )

        self.pipeline.fit(X_treated, y_treated)
        self.is_fitted = True
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Predict probability of transaction under offer (p_treat).

        Args:
            df: DataFrame containing required feature columns.

        Returns:
            1D NumPy array of predicted probabilities P(Y=1 | X, T=1).

        Raises:
            RuntimeError: If model is not fitted yet.
        """
        if not self.is_fitted or self.pipeline is None:
            raise RuntimeError("Model is not fitted yet. Call fit() before predict_proba().")

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Input DataFrame is missing feature columns: {missing}")

        X = df[self.feature_cols]
        # Column 1 is probability of positive transaction outcome (class 1)
        probas = self.pipeline.predict_proba(X)[:, 1]
        return probas

    def evaluate(self, val_df: pd.DataFrame, eval_type: str = "smoke") -> BaselineEvaluationResult:
        """Evaluate baseline model on validation split.

        Computes discriminatory power (AUC) and calibration (Brier score) on validation customers.

        Args:
            val_df: Validation DataFrame.
            eval_type: String tag for run type ('smoke', 'ml_dev', 'benchmark').

        Returns:
            BaselineEvaluationResult with observed metrics.
        """
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet. Call fit() before evaluate().")

        # Predict p_treat for all validation rows
        p_treat = self.predict_proba(val_df)

        # Calculate AUC and Brier score specifically on treated validation customers
        # where the factual outcome observed was under treatment
        treated_mask = (val_df[TREATMENT_COLUMN] == 1).values
        n_treated = int(np.sum(treated_mask))

        auc_score: Optional[float] = None
        brier_val: float

        if n_treated > 0:
            y_treated_val = val_df.loc[treated_mask, TARGET_COLUMN].values
            p_treated_val = p_treat[treated_mask]

            # AUC requires both positive and negative outcomes in the evaluation slice
            if len(np.unique(y_treated_val)) > 1:
                auc_score = float(roc_auc_score(y_treated_val, p_treated_val))

            brier_val = float(brier_score_loss(y_treated_val, p_treated_val))
        else:
            # Fallback across all validation rows if treated subset is empty
            y_all_val = val_df[TARGET_COLUMN].values
            if len(np.unique(y_all_val)) > 1:
                auc_score = float(roc_auc_score(y_all_val, p_treat))
            brier_val = float(brier_score_loss(y_all_val, p_treat))

        return BaselineEvaluationResult(
            auc=auc_score,
            brier_score=brier_val,
            mean_p_treat=float(np.mean(p_treat)),
            min_p_treat=float(np.min(p_treat)),
            max_p_treat=float(np.max(p_treat)),
            n_eval_total=len(val_df),
            n_eval_treated=n_treated,
            eval_type=eval_type,
        )

    def score_test(self, test_df: pd.DataFrame) -> BaselineEvaluationResult:
        """Score the held-out test split once for final benchmark reporting.

        CRITICAL PROTOCOL NOTICE: This method is intended to be called ONLY ONCE during
        final release evaluation (Step 15.4 / 16). It must not be called during iterative tuning.

        Args:
            test_df: Held-out test split DataFrame.

        Returns:
            BaselineEvaluationResult on test set.
        """
        return self.evaluate(test_df, eval_type="test_evaluation")


def train_response_baseline(
    train_df: pd.DataFrame,
    random_state: int = 20261006,
) -> ResponseBaselineModel:
    """Convenience helper to instantiate and fit a ResponseBaselineModel.

    Args:
        train_df: Training DataFrame.
        random_state: Reproducibility seed.

    Returns:
        Fitted ResponseBaselineModel.
    """
    model = ResponseBaselineModel(random_state=random_state)
    model.fit(train_df)
    return model


def run_smoke_baseline(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    output_metrics_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Execute smoke validation run for Response Baseline on fixture/dev data.

    Args:
        dataset_dir: Directory containing features and splits (default: fixture_v1).
        output_metrics_path: Optional destination to write smoke_baseline_metrics.json.

    Returns:
        Evaluation metrics dictionary marked as 'smoke'.
    """
    train_df, val_df = load_train_val(dataset_dir)
    model = train_response_baseline(train_df)
    eval_result = model.evaluate(val_df, eval_type="smoke")
    result_dict = eval_result.to_dict()

    if output_metrics_path:
        out_p = Path(output_metrics_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2)

    return result_dict


if __name__ == "__main__":
    metrics = run_smoke_baseline()
    print("Response Baseline Smoke Metrics:")
    print(json.dumps(metrics, indent=2))
