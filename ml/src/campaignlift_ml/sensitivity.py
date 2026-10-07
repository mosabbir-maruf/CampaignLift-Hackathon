"""Seed and Assignment Sensitivity Evaluation module for CampaignLift.

Evaluates:
1. Repeated-seed AUUC spread across 5 random seeds to demonstrate stability.
2. Treatment assignment distribution shift sensitivity comparing:
   - Response propensity (Candidate B0)
   - Logistic T-Learner (Candidate U0)
   - LightGBM S-Learner (Winning Candidate U2, frozen artifact)
   under baseline (p=0.5) and shifted (p=0.3) treatment assignment rates.

Causal Governance:
- Frozen deployed model remains cl-model-ml_dev_20261006-lgbm_s_learner-r01.
- No new champion model declared.
- All metrics computed strictly via canonical functions in metrics.py.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .artifact import load_model_artifact
from .baseline import ResponseBaselineModel
from .data import TARGET_COLUMN, TREATMENT_COLUMN, load_train_val
from .metrics import (
    compute_qini_curve,
    compute_top_decile_incremental_response,
)
from .uplift import (
    LightGBMSLearner,
    train_lightgbm_s_learner,
    train_logistic_t_learner,
)

DEFAULT_SEEDS = [20261006, 20261007, 20261008, 20261009, 20261010]
DEFAULT_SHIFTED_TREATMENT_RATE = 0.30


def run_repeated_seeds_evaluation(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    seeds: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Train LightGBM S-Learner across 5 random seeds and report validation AUUC spread."""
    seeds_list = seeds or DEFAULT_SEEDS
    seed_records: List[Dict[str, Any]] = []
    auuc_values: List[float] = []

    y_val = val_df[TARGET_COLUMN].values
    t_val = val_df[TREATMENT_COLUMN].values

    for s in seeds_list:
        try:
            # Seeded training draw with replacement to test seed stability
            rng = np.random.default_rng(s)
            idx = rng.choice(len(train_df), size=len(train_df), replace=True)
            train_seeded = train_df.iloc[idx].reset_index(drop=True)

            model = train_lightgbm_s_learner(train_seeded, random_state=s)
            preds = model.predict_uplift(val_df)

            qini_res = compute_qini_curve(y_val, preds.uplift, t_val)
            auuc = (
                float(qini_res.normalized_qini_score)
                if qini_res.normalized_qini_score is not None
                else 0.0
            )
            qini_score = float(qini_res.qini_score)

            seed_records.append({
                "seed": s,
                "model": "lightgbm_s_learner",
                "validation_auuc": round(auuc, 4),
                "validation_qini": round(qini_score, 4),
                "n_train": len(train_seeded),
                "n_val": len(val_df),
                "status": "completed",
            })
            auuc_values.append(auuc)
        except Exception as err:
            seed_records.append({
                "seed": s,
                "model": "lightgbm_s_learner",
                "validation_auuc": None,
                "validation_qini": None,
                "status": f"failed: {err}",
            })

    if not auuc_values:
        raise RuntimeError("No seed evaluations completed successfully.")

    auuc_arr = np.array(auuc_values)
    summary = {
        "seeds_requested": len(seeds_list),
        "seeds_completed": len(auuc_values),
        "mean_auuc": round(float(np.mean(auuc_arr)), 4),
        "std_auuc": round(float(np.std(auuc_arr)), 4),
        "min_auuc": round(float(np.min(auuc_arr)), 4),
        "max_auuc": round(float(np.max(auuc_arr)), 4),
        "auuc_spread": round(float(np.max(auuc_arr) - np.min(auuc_arr)), 4),
    }

    return {
        "summary": summary,
        "seed_results": seed_records,
    }


def create_shifted_validation_cohort(
    val_df: pd.DataFrame,
    target_treatment_rate: float = DEFAULT_SHIFTED_TREATMENT_RATE,
    seed: int = 20261006,
) -> pd.DataFrame:
    """Create a validation cohort under shifted treatment assignment probability."""
    ctrl_indices = val_df[val_df[TREATMENT_COLUMN] == 0].index.tolist()
    treat_indices = val_df[val_df[TREATMENT_COLUMN] == 1].index.tolist()

    if len(ctrl_indices) == 0 or len(treat_indices) == 0:
        raise ValueError("Validation DataFrame must contain both treatment arms.")

    # Calculate desired treated count: N_t = N_c * p / (1 - p)
    n_ctrl = len(ctrl_indices)
    desired_n_treat = max(2, int(round(n_ctrl * target_treatment_rate / (1.0 - target_treatment_rate))))
    n_treat_to_keep = min(len(treat_indices), desired_n_treat)

    rng = np.random.default_rng(seed)
    chosen_treat = rng.choice(treat_indices, size=n_treat_to_keep, replace=False).tolist()

    shifted_indices = ctrl_indices + chosen_treat
    shifted_df = val_df.loc[shifted_indices].reset_index(drop=True)
    return shifted_df


def run_assignment_sensitivity_comparison(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    shifted_val_df: pd.DataFrame,
    artifact_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Compare response propensity, logistic T-learner, and LightGBM S-learner across conditions."""
    # Fit baseline models on training split
    b0_model = ResponseBaselineModel().fit(train_df)
    u0_model = train_logistic_t_learner(train_df)
    u2_artifact = load_model_artifact(artifact_dir)

    comparison_rows: List[Dict[str, Any]] = []

    eval_conditions = [
        ("baseline_rct (p=0.5)", val_df),
        (f"shifted_assignment (p={DEFAULT_SHIFTED_TREATMENT_RATE})", shifted_val_df),
    ]

    for condition_name, eval_df in eval_conditions:
        y = eval_df[TARGET_COLUMN].values
        t = eval_df[TREATMENT_COLUMN].values
        n = len(eval_df)

        # 1. Response Propensity (Rank by p_treat descending)
        p_b0 = b0_model.predict_proba(eval_df)
        q_b0 = compute_qini_curve(y, p_b0, t)
        top_b0 = compute_top_decile_incremental_response(y, p_b0, t, min_support=1)
        inc_b0 = (
            float(top_b0.incremental_rate)
            if top_b0.incremental_rate is not None
            else 0.0
        )
        comparison_rows.append({
            "condition": condition_name,
            "model": "response_propensity",
            "AUUC": round(q_b0.normalized_qini_score or 0.0, 4),
            "top_decile_incremental_rate": round(inc_b0, 4),
            "n": n,
        })

        # 2. Logistic T-Learner (Rank by predicted uplift descending)
        preds_u0 = u0_model.predict_uplift(eval_df)
        q_u0 = compute_qini_curve(y, preds_u0.uplift, t)
        top_u0 = compute_top_decile_incremental_response(y, preds_u0.uplift, t, min_support=1)
        inc_u0 = (
            float(top_u0.incremental_rate)
            if top_u0.incremental_rate is not None
            else 0.0
        )
        comparison_rows.append({
            "condition": condition_name,
            "model": "logistic_t_learner",
            "AUUC": round(q_u0.normalized_qini_score or 0.0, 4),
            "top_decile_incremental_rate": round(inc_u0, 4),
            "n": n,
        })

        # 3. LightGBM S-Learner (Frozen production model)
        preds_u2 = u2_artifact.predict_uplift(eval_df)
        q_u2 = compute_qini_curve(y, preds_u2.uplift, t)
        top_u2 = compute_top_decile_incremental_response(y, preds_u2.uplift, t, min_support=1)
        inc_u2 = (
            float(top_u2.incremental_rate)
            if top_u2.incremental_rate is not None
            else 0.0
        )
        comparison_rows.append({
            "condition": condition_name,
            "model": "lightgbm_s_learner",
            "AUUC": round(q_u2.normalized_qini_score or 0.0, 4),
            "top_decile_incremental_rate": round(inc_u2, 4),
            "n": n,
        })

    return comparison_rows


def run_sensitivity_pipeline(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    artifact_dir: Optional[Union[str, Path]] = None,
    seeds: Optional[List[int]] = None,
    target_treatment_rate: float = DEFAULT_SHIFTED_TREATMENT_RATE,
    output_path: Optional[Union[str, Path]] = "docs/sensitivity_analysis.json",
) -> Dict[str, Any]:
    """Execute complete seed and assignment sensitivity pipeline."""
    train_df, val_df = load_train_val(dataset_dir)
    shifted_val_df = create_shifted_validation_cohort(
        val_df=val_df,
        target_treatment_rate=target_treatment_rate,
        seed=20261006,
    )

    # 1. 5-seed stability evaluation
    seed_eval = run_repeated_seeds_evaluation(train_df, val_df, seeds=seeds)

    # 2. Assignment shift comparison
    comparison_table = run_assignment_sensitivity_comparison(
        train_df=train_df,
        val_df=val_df,
        shifted_val_df=shifted_val_df,
        artifact_dir=artifact_dir,
    )

    report = {
        "report_version": "1.0",
        "evaluation_name": "Repeated-Seed Stability and Assignment Sensitivity",
        "dataset_dir": str(dataset_dir),
        "frozen_model": "cl-model-ml_dev_20261006-lgbm_s_learner-r01",
        "champion_status": "unchanged",
        "repeated_seeds": seed_eval,
        "assignment_sensitivity": {
            "target_shifted_treatment_rate": target_treatment_rate,
            "table_columns": ["condition", "model", "AUUC", "top_decile_incremental_rate", "n"],
            "comparison_table": comparison_table,
        },
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run repeated seeds and assignment sensitivity evaluation.")
    parser.add_argument("--dataset-dir", default="data/fixtures/fixture_v1", help="Dataset directory")
    parser.add_argument("--output", default="docs/sensitivity_analysis.json", help="Output JSON path")
    args, _ = parser.parse_known_args()

    results = run_sensitivity_pipeline(
        dataset_dir=args.dataset_dir,
        output_path=args.output,
    )

    print("=== Repeated-Seed AUUC Evaluation ===")
    summ = results["repeated_seeds"]["summary"]
    print(f"Seeds completed: {summ['seeds_completed']}/{summ['seeds_requested']}")
    print(f"Mean AUUC: {summ['mean_auuc']:.4f}, Std: {summ['std_auuc']:.4f}, Spread [min, max]: [{summ['min_auuc']:.4f}, {summ['max_auuc']:.4f}]")
    for r in results["repeated_seeds"]["seed_results"]:
        print(f"  Seed {r['seed']}: AUUC = {r['validation_auuc']}")

    print("\n=== Treatment Assignment Sensitivity Comparison ===")
    print(f"{'Condition':<30} {'Model':<22} {'AUUC':<10} {'TopDecileInc':<15} {'N':<6}")
    print("-" * 85)
    for row in results["assignment_sensitivity"]["comparison_table"]:
        print(f"{row['condition']:<30} {row['model']:<22} {row['AUUC']:<10.4f} {row['top_decile_incremental_rate']:<15.4f} {row['n']:<6}")
    print(f"\nReport written to: {args.output}")
