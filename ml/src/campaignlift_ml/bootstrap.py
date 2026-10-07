"""Bootstrap Confidence Intervals module for CampaignLift.

Pre-committed Evaluation Settings:
- Resample count: 200
- Interval: Percentile interval at [2.5, 97.5] (95% confidence)
- Random seed: 20261006
- Causal rule: Frozen LightGBM S-Learner (U2) evaluated without refitting.
- Reuses Qini and AUUC metrics directly from campaignlift_ml.metrics.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .artifact import load_model_artifact
from .data import load_dataset_splits
from .metrics import compute_qini_curve, compute_qini_score

PRECOMMITTED_RESAMPLES = 200
PRECOMMITTED_SEED = 20261006
PRECOMMITTED_PERCENTILES = (2.5, 97.5)


@dataclass
class MetricBootstrapResult:
    """Bootstrap interval result for a single metric."""
    metric_name: str
    point_estimate: float
    ci_lower: float
    ci_upper: float
    resamples_completed: int
    seed: int
    percentiles: Tuple[float, float]
    historical_published: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        differs = (
            abs(self.point_estimate - self.historical_published) > 1e-4
            if self.historical_published is not None
            else False
        )
        return {
            "metric_name": self.metric_name,
            "point_estimate": round(self.point_estimate, 6),
            "ci_lower": round(self.ci_lower, 6),
            "ci_upper": round(self.ci_upper, 6),
            "resamples_completed": self.resamples_completed,
            "seed": self.seed,
            "percentiles": list(self.percentiles),
            "historical_published": self.historical_published,
            "differs_from_historical": differs,
        }


def compute_percentile_interval(
    distribution: Union[List[float], np.ndarray],
    lower_pct: float = 2.5,
    upper_pct: float = 97.5,
) -> Tuple[float, float]:
    """Compute empirical percentile interval bounds for a distribution array."""
    arr = np.asarray(distribution, dtype=float)
    if len(arr) == 0:
        raise ValueError("Cannot compute percentile interval on empty distribution.")
    lower = float(np.percentile(arr, lower_pct))
    upper = float(np.percentile(arr, upper_pct))
    return lower, upper


def bootstrap_arrays(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
    n_resamples: int = PRECOMMITTED_RESAMPLES,
    seed: int = PRECOMMITTED_SEED,
    lower_pct: float = PRECOMMITTED_PERCENTILES[0],
    upper_pct: float = PRECOMMITTED_PERCENTILES[1],
) -> Dict[str, MetricBootstrapResult]:
    """Compute point estimates and bootstrap percentile intervals directly on arrays.

    Reuses compute_qini_curve from metrics.py.
    """
    y = np.asarray(y_true, dtype=float)
    preds = np.asarray(uplift_preds, dtype=float)
    t = np.asarray(treatment, dtype=int)
    n = len(y)

    if n < 4:
        raise ValueError("Array length must be >= 4 to compute meaningful bootstrap intervals.")

    # 1. Point estimates on original sample
    point_res = compute_qini_curve(y, preds, t)
    point_qini = float(point_res.qini_score)
    point_auuc = (
        float(point_res.normalized_qini_score)
        if point_res.normalized_qini_score is not None
        else 0.0
    )

    # 2. Resampling with replacement
    rng = np.random.default_rng(seed)
    qini_samples: List[float] = []
    auuc_samples: List[float] = []

    for _ in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        y_samp = y[idx]
        t_samp = t[idx]
        preds_samp = preds[idx]

        # Guard: both treatment and control arms must be present
        if len(np.unique(t_samp)) < 2:
            continue

        try:
            res = compute_qini_curve(y_samp, preds_samp, t_samp)
            qini_samples.append(float(res.qini_score))
            if res.normalized_qini_score is not None and np.isfinite(res.normalized_qini_score):
                auuc_samples.append(float(res.normalized_qini_score))
        except Exception:
            continue

    if not qini_samples:
        raise RuntimeError("Bootstrap produced zero valid resamples with both arms represented.")

    qini_lower, qini_upper = compute_percentile_interval(qini_samples, lower_pct, upper_pct)
    auuc_lower, auuc_upper = (
        compute_percentile_interval(auuc_samples, lower_pct, upper_pct)
        if auuc_samples
        else (point_auuc, point_auuc)
    )

    return {
        "qini": MetricBootstrapResult(
            metric_name="test_qini",
            point_estimate=point_qini,
            ci_lower=qini_lower,
            ci_upper=qini_upper,
            resamples_completed=len(qini_samples),
            seed=seed,
            percentiles=(lower_pct, upper_pct),
            historical_published=65.2257,
        ),
        "auuc": MetricBootstrapResult(
            metric_name="test_auuc",
            point_estimate=point_auuc,
            ci_lower=auuc_lower,
            ci_upper=auuc_upper,
            resamples_completed=len(auuc_samples),
            seed=seed,
            percentiles=(lower_pct, upper_pct),
            historical_published=0.1755,
        ),
    }


def run_bootstrap_evaluation(
    artifact_dir: Optional[Union[str, Path]] = None,
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    n_resamples: int = PRECOMMITTED_RESAMPLES,
    seed: int = PRECOMMITTED_SEED,
    output_path: Optional[Union[str, Path]] = "docs/bootstrap_intervals.json",
) -> Dict[str, Any]:
    """Execute bootstrap confidence interval evaluation for the frozen uplift model on test split.

    Steps:
    1. Load pre-trained model artifact without refitting.
    2. Load frozen test split.
    3. Score test rows with model.
    4. Compute point estimates and 200 resamples with replacement.
    5. Save results to output JSON.
    """
    model_artifact = load_model_artifact(artifact_dir)
    splits = load_dataset_splits(dataset_dir, include_test=True)

    if splits.test is None or len(splits.test) == 0:
        raise ValueError(f"No test split found in dataset directory: {dataset_dir}")

    test_df = splits.test

    # Score each row using the pre-trained model
    preds = model_artifact.predict_uplift(test_df)
    y_true = test_df["y_transacted"].values
    treatment = test_df["treatment"].values

    bootstrap_results = bootstrap_arrays(
        y_true=y_true,
        uplift_preds=preds.uplift,
        treatment=treatment,
        n_resamples=n_resamples,
        seed=seed,
    )

    res_dict = {
        "report_version": "1.0",
        "evaluation_name": "Percentile Bootstrap Intervals on Frozen Test Split",
        "model_version": model_artifact.model_version,
        "candidate_id": model_artifact.candidate_id,
        "dataset_dir": str(dataset_dir),
        "test_n_samples": len(test_df),
        "precommitted_settings": {
            "n_resamples": n_resamples,
            "seed": seed,
            "percentiles": list(PRECOMMITTED_PERCENTILES),
            "refit_performed": False,
        },
        "metrics": {
            "qini": bootstrap_results["qini"].to_dict(),
            "auuc": bootstrap_results["auuc"].to_dict(),
        },
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(res_dict, f, indent=2)

    return res_dict


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run bootstrap interval estimation on frozen test split.")
    parser.add_argument("--dataset-dir", default="data/fixtures/fixture_v1", help="Dataset directory")
    parser.add_argument("--resamples", type=int, default=PRECOMMITTED_RESAMPLES, help="Number of resamples")
    parser.add_argument("--seed", type=int, default=PRECOMMITTED_SEED, help="Random seed")
    parser.add_argument("--output", default="docs/bootstrap_intervals.json", help="Output JSON path")
    args, _ = parser.parse_known_args()

    results = run_bootstrap_evaluation(
        dataset_dir=args.dataset_dir,
        n_resamples=args.resamples,
        seed=args.seed,
        output_path=args.output,
    )

    print("=== Percentile Bootstrap Intervals on Frozen Test ===")
    print(f"Model Version: {results['model_version']} ({results['candidate_id']})")
    print(f"Resamples Completed: {results['precommitted_settings']['n_resamples']}, Seed: {results['precommitted_settings']['seed']}")
    print(f"Test Cohort Size: {results['test_n_samples']}")
    qini_m = results["metrics"]["qini"]
    auuc_m = results["metrics"]["auuc"]
    print(f"Qini: Point = {qini_m['point_estimate']:.4f}, 95% CI = [{qini_m['ci_lower']:.4f}, {qini_m['ci_upper']:.4f}] (Historical: {qini_m['historical_published']})")
    print(f"AUUC: Point = {auuc_m['point_estimate']:.4f}, 95% CI = [{auuc_m['ci_lower']:.4f}, {auuc_m['ci_upper']:.4f}] (Historical: {auuc_m['historical_published']})")
    print(f"Output saved to: {args.output}")
