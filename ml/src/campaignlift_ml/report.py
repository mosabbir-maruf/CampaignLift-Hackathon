"""Validation Reporting & Responsible AI Segments module for CampaignLift.

Outputs:
1. Overall causal uplift evaluation (Qini score, ATE, treatment rate).
2. Segment fairness & stability error analysis across demographic and behavioral slices:
   - 'age_band'
   - 'region_code'
   - 'kyc_level'
   - 'activity_band' (derived from txn_count_30d: 0, 1-4, 5+)
   - 'prior_exposure_band' (derived from campaign_exposures: 0, 1-2, 3+)
   Enforcing the 30/30 minimum randomized support rule on every slice.
3. Optional Synthetic-Oracle evaluation (run only when hidden oracle file is explicitly supplied):
   - Spearman rank correlation of predicted uplift vs true_uplift
   - Mean true_uplift in top decile of predicted uplift
   - Mean true_uplift among customers picked by response model
   - Explicitly labeled 'synthetic_oracle' with caveats.

Strict Causal & Responsible AI Rules:
- Never join hidden/oracle columns into the training frame or feature matrices.
- An evaluation without the hidden oracle file must run cleanly and emit all standard Qini & slice metrics.
- Oracle metrics must never be reported as proof of causal effect on real deploy data.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .data import (
    CATEGORICAL_COLUMNS,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    assert_no_forbidden_columns,
    load_train_val,
)
from .metrics import (
    compute_incremental_response,
    compute_qini_curve,
    compute_treatment_rate,
    evaluate_uplift_predictions,
)


# -----------------------------------------------------------------------------
# Band Derivations
# -----------------------------------------------------------------------------

def derive_activity_band(txn_count_30d: Union[int, float, pd.Series, np.ndarray]) -> Union[str, pd.Series]:
    """Derive activity band from 30-day transaction count: 0, 1-4, 5+."""
    if isinstance(txn_count_30d, pd.Series):
        conditions = [
            txn_count_30d == 0,
            (txn_count_30d >= 1) & (txn_count_30d <= 4),
            txn_count_30d >= 5,
        ]
        choices = ["0", "1-4", "5+"]
        return pd.Series(np.select(conditions, choices, default="0"), index=txn_count_30d.index)

    val = float(txn_count_30d)
    if val <= 0:
        return "0"
    elif val <= 4:
        return "1-4"
    else:
        return "5+"


def derive_prior_exposure_band(exposures: Union[int, float, pd.Series, np.ndarray]) -> Union[str, pd.Series]:
    """Derive prior exposure band: 0, 1-2, 3+."""
    if isinstance(exposures, pd.Series):
        conditions = [
            exposures == 0,
            (exposures >= 1) & (exposures <= 2),
            exposures >= 3,
        ]
        choices = ["0", "1-2", "3+"]
        return pd.Series(np.select(conditions, choices, default="0"), index=exposures.index)

    val = float(exposures)
    if val <= 0:
        return "0"
    elif val <= 2:
        return "1-2"
    else:
        return "3+"


# -----------------------------------------------------------------------------
# Segment Analysis
# -----------------------------------------------------------------------------

def analyze_segment_slices(
    val_df: pd.DataFrame,
    uplift_preds: Union[np.ndarray, pd.Series],
    p_treat: Optional[Union[np.ndarray, pd.Series]] = None,
    min_support: int = 30,
) -> Dict[str, Dict[str, Any]]:
    """Compute fairness and stability metrics across demographic and behavioral slices.

    Slices:
    - age_band
    - region_code
    - kyc_level
    - activity_band
    - prior_exposure_band
    """
    df = val_df.copy()
    df["predicted_uplift"] = np.asarray(uplift_preds, dtype=float)
    if p_treat is not None:
        df["predicted_response"] = np.asarray(p_treat, dtype=float)

    # Derive activity band
    if "txn_count_30d" in df.columns:
        df["activity_band"] = derive_activity_band(df["txn_count_30d"])
    else:
        df["activity_band"] = "0"

    # Derive prior exposure band
    if "campaign_exposures_prior_90d" in df.columns:
        df["prior_exposure_band"] = derive_prior_exposure_band(df["campaign_exposures_prior_90d"])
    elif "campaign_exposures_prior_30d" in df.columns:
        df["prior_exposure_band"] = derive_prior_exposure_band(df["campaign_exposures_prior_30d"])
    else:
        df["prior_exposure_band"] = "0"

    slice_cols = [
        "age_band",
        "region_code",
        "kyc_level",
        "activity_band",
        "prior_exposure_band",
    ]

    segments_report: Dict[str, Dict[str, Any]] = {}

    for slice_col in slice_cols:
        if slice_col not in df.columns:
            continue

        slice_dict: Dict[str, Any] = {}
        for category, sub_df in df.groupby(slice_col, observed=False):
            cat_name = str(category)
            n_sub = len(sub_df)
            if n_sub == 0:
                continue

            sub_t = sub_df[TREATMENT_COLUMN].values if TREATMENT_COLUMN in sub_df.columns else np.array([])
            sub_y = sub_df[TARGET_COLUMN].values if TARGET_COLUMN in sub_df.columns else np.array([])
            sub_preds = sub_df["predicted_uplift"].values

            n_t = int(np.sum(sub_t == 1))
            n_c = int(np.sum(sub_t == 0))
            treatment_rate = float(n_t / n_sub) if n_sub > 0 else 0.0

            # Support check & factual incremental rate
            if len(sub_y) > 0 and len(sub_t) > 0:
                inc_resp = compute_incremental_response(sub_y, sub_t, min_support=min_support)
                # Compute slice Qini if both arms have at least 2 observations
                if n_t >= 2 and n_c >= 2:
                    try:
                        qini_res = compute_qini_curve(sub_y, sub_preds, sub_t)
                        slice_qini = round(qini_res.qini_score, 4)
                    except Exception:
                        slice_qini = None
                else:
                    slice_qini = None
            else:
                inc_resp = None
                slice_qini = None

            mean_pred_uplift = float(np.mean(sub_preds))
            mean_pred_response = (
                float(np.mean(sub_df["predicted_response"]))
                if "predicted_response" in sub_df.columns
                else None
            )

            slice_dict[cat_name] = {
                "n_samples": n_sub,
                "n_treated": n_t,
                "n_control": n_c,
                "treatment_rate": round(treatment_rate, 4),
                "mean_predicted_uplift": round(mean_pred_uplift, 5),
                "mean_predicted_response": round(mean_pred_response, 5) if mean_pred_response is not None else None,
                "slice_qini_score": slice_qini,
                "incremental_response": inc_resp.to_dict() if inc_resp is not None else None,
            }

        segments_report[slice_col] = slice_dict

    return segments_report


# -----------------------------------------------------------------------------
# Synthetic Oracle Evaluation
# -----------------------------------------------------------------------------

def evaluate_synthetic_oracle(
    val_df: pd.DataFrame,
    uplift_preds: Union[np.ndarray, pd.Series],
    p_treat: Optional[Union[np.ndarray, pd.Series]] = None,
    hidden_df_or_path: Optional[Union[pd.DataFrame, str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Compute benchmark comparison against synthetic oracle true_uplift.

    Note:
    - This is ONLY permitted for synthetic benchmark evaluations.
    - All emitted metrics are explicitly marked 'synthetic_oracle'.
    - If hidden_df_or_path is None or file does not exist, returns None.
    """
    if hidden_df_or_path is None:
        return None

    if isinstance(hidden_df_or_path, (str, Path)):
        p = Path(hidden_df_or_path)
        if not p.is_file():
            return None
        with p.open("r", encoding="utf-8") as f:
            raw_hidden = json.load(f)
        hidden_df = pd.DataFrame(raw_hidden)
    else:
        hidden_df = hidden_df_or_path.copy()

    if "true_uplift" not in hidden_df.columns:
        return None

    # Merge on customer_id if present, else align by index
    eval_preds = np.asarray(uplift_preds, dtype=float)

    if "customer_id" in val_df.columns and "customer_id" in hidden_df.columns:
        merged = pd.merge(
            val_df[["customer_id"]].assign(pred_uplift=eval_preds),
            hidden_df[["customer_id", "true_uplift"]],
            on="customer_id",
            how="inner",
        )
        if len(merged) == 0:
            return None
        y_true_uplift = merged["true_uplift"].values
        y_pred_uplift = merged["pred_uplift"].values
    else:
        # Align by common length
        n = min(len(val_df), len(hidden_df))
        y_true_uplift = hidden_df["true_uplift"].iloc[:n].values
        y_pred_uplift = eval_preds[:n]

    # 1. Spearman Rank Correlation
    try:
        from scipy.stats import spearmanr
        res = spearmanr(y_pred_uplift, y_true_uplift)
        spearman_corr = float(res.statistic if hasattr(res, "statistic") else res[0])
    except Exception:
        # Pure numpy rank correlation fallback
        def _rank(a):
            return np.argsort(np.argsort(a))
        r_pred = _rank(y_pred_uplift)
        r_true = _rank(y_true_uplift)
        spearman_corr = float(np.corrcoef(r_pred, r_true)[0, 1])

    # 2. Mean true_uplift in top decile of predicted uplift
    order = np.argsort(-y_pred_uplift, kind="mergesort")
    top_decile_n = max(1, int(np.ceil(0.10 * len(y_pred_uplift))))
    top_decile_idx = order[:top_decile_n]
    mean_true_uplift_top_decile = float(np.mean(y_true_uplift[top_decile_idx]))

    # 3. Mean true_uplift among customers picked by response model (p_treat)
    if p_treat is not None:
        p_treat_arr = np.asarray(p_treat, dtype=float)[:len(y_true_uplift)]
        resp_order = np.argsort(-p_treat_arr, kind="mergesort")
        resp_top_decile_idx = resp_order[:top_decile_n]
        mean_true_uplift_response_model = float(np.mean(y_true_uplift[resp_top_decile_idx]))
    else:
        mean_true_uplift_response_model = None

    return {
        "label": "synthetic_oracle",
        "caveat": "Synthetic benchmark metric only; unobservable in real production data.",
        "n_evaluated": len(y_true_uplift),
        "spearman_rank_correlation": round(spearman_corr, 5),
        "mean_true_uplift_overall": round(float(np.mean(y_true_uplift)), 5),
        "mean_true_uplift_top_decile_predicted_uplift": round(mean_true_uplift_top_decile, 5),
        "mean_true_uplift_top_decile_response_model": (
            round(mean_true_uplift_response_model, 5)
            if mean_true_uplift_response_model is not None
            else None
        ),
    }


# -----------------------------------------------------------------------------
# Complete Validation Report Generator
# -----------------------------------------------------------------------------

def generate_validation_report(
    val_df: pd.DataFrame,
    uplift_preds: Union[np.ndarray, pd.Series],
    p_treat: Optional[Union[np.ndarray, pd.Series]] = None,
    candidate_id: str = "U0",
    model_name: str = "uplift_model",
    hidden_uplift_path: Optional[Union[str, Path]] = None,
    output_path: Optional[Union[str, Path]] = None,
    min_support: int = 30,
    evaluation_name: str = "Fairness Slice Evaluation",
    run_id: Optional[str] = None,
    population_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate the full validation report including Qini, segments, and optional oracle block.

    Args:
        val_df: Validation DataFrame (features, treatment, y_transacted).
        uplift_preds: Predicted uplift array (tau_hat).
        p_treat: Optional predicted response array.
        candidate_id: Model candidate ID (e.g., 'U0', 'U1').
        model_name: Model descriptor name.
        hidden_uplift_path: Optional path to hidden_uplift.json for synthetic oracle checks.
        output_path: Optional path to save the generated JSON report.
        min_support: Minimum treated and control customers for reliable slice effect reporting (30).
        evaluation_name: Name of the evaluation procedure (default: 'Fairness Slice Evaluation').
        run_id: Unique identifier for the evaluation run.
        population_name: Identifier of the evaluated population cohort.

    Returns:
        JSON-serializable report dictionary.
    """
    assert_no_forbidden_columns(val_df)

    y_true = val_df[TARGET_COLUMN].values
    treatment = val_df[TREATMENT_COLUMN].values
    preds = np.asarray(uplift_preds, dtype=float)

    # 1. Overall Uplift & Qini Evaluation Block (Always present)
    overall_block = evaluate_uplift_predictions(
        y_true=y_true,
        uplift_preds=preds,
        treatment=treatment,
        candidate_id=candidate_id,
        model_name=model_name,
        min_support=min_support,
    )

    # 2. Responsible AI Demographic & Behavioral Slices
    segments_block = analyze_segment_slices(
        val_df=val_df,
        uplift_preds=preds,
        p_treat=p_treat,
        min_support=min_support,
    )

    # 3. Optional Synthetic Oracle Evaluation (Only if file passed)
    oracle_block = evaluate_synthetic_oracle(
        val_df=val_df,
        uplift_preds=preds,
        p_treat=p_treat,
        hidden_df_or_path=hidden_uplift_path,
    )

    resolved_run_id = run_id or "run_fairness_slice_fixture_v1"
    resolved_population = population_name or "fixture_v1"

    report = {
        "report_version": "1.0",
        "evaluation_name": evaluation_name,
        "run_id": resolved_run_id,
        "population_name": resolved_population,
        "row_count": len(val_df),
        "candidate_id": candidate_id,
        "model_name": model_name,
        "overall_metrics": overall_block,
        "segments": segments_block,
        "synthetic_oracle": oracle_block,
    }

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


def run_smoke_validation_report(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    include_oracle: bool = True,
    output_path: Optional[Union[str, Path]] = None,
    run_id: str = "run_fairness_slice_fixture_v1",
) -> Dict[str, Any]:
    """Execute smoke validation report generation for candidate U0 on fixture data."""
    from .uplift import train_logistic_t_learner

    train_df, val_df = load_train_val(dataset_dir)
    learner = train_logistic_t_learner(train_df)
    preds = learner.predict_uplift(val_df)

    p_hidden = (
        Path(dataset_dir) / "hidden_uplift.json"
        if include_oracle
        else None
    )

    pop_name = Path(dataset_dir).name
    return generate_validation_report(
        val_df=val_df,
        uplift_preds=preds.uplift,
        p_treat=preds.p_treat,
        candidate_id=learner.candidate_id,
        model_name=learner.model_name,
        hidden_uplift_path=p_hidden,
        output_path=output_path,
        evaluation_name="Fairness Slice Evaluation",
        run_id=run_id,
        population_name=pop_name,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Fairness Slice Evaluation report.")
    parser.add_argument("--dataset-dir", default="data/fixtures/fixture_v1", help="Dataset directory")
    parser.add_argument(
        "--output",
        default="docs/fairness_slice_evaluation.json",
        help="Path to output JSON result file",
    )
    parser.add_argument("--run-id", default="run_fairness_slice_fixture_v1", help="Evaluation run ID")
    parser.add_argument("--no-oracle", action="store_true", help="Exclude synthetic oracle evaluation")
    args, _ = parser.parse_known_args()

    # Generate and write Fairness Slice Evaluation
    report = run_smoke_validation_report(
        dataset_dir=args.dataset_dir,
        include_oracle=not args.no_oracle,
        output_path=args.output,
        run_id=args.run_id,
    )

    print("=== Fairness Slice Evaluation ===")
    print(f"Run ID: {report['run_id']}")
    print(f"Population: {report['population_name']} ({report['row_count']} validation rows)")
    print(f"Result file: {args.output}")
    print(f"Overall Qini: {report['overall_metrics']['qini_score']}")
    print(f"Evaluated slices: {list(report['segments'].keys())}")
    if report["synthetic_oracle"]:
        print(f"Synthetic Oracle Spearman: {report['synthetic_oracle']['spearman_rank_correlation']}")
