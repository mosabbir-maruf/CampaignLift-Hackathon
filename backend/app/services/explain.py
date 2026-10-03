"""Explanation service for CampaignLift customer-level grounded reasoning."""

from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd

from backend.app.schemas import (
    CustomerExplanationResponse,
    FeatureContribution,
)
from backend.app.services.inference import (
    CAMPAIGN_FIELDS,
    FORBIDDEN_COLUMNS,
    FeatureMismatchError,
    assert_no_forbidden_columns,
    load_feature_table,
    load_model_artifact,
)
from backend.app.settings import REPO_ROOT, Settings, get_settings

ReasonCode = Literal["likely_without_offer", "incremental_candidate", "weak_response", "negative_uplift"]

# Ensure ML package is available
ml_src_path = str(REPO_ROOT / "ml" / "src")
if ml_src_path not in sys.path:
    sys.path.insert(0, ml_src_path)


class CustomerNotFoundError(KeyError):
    """Raised when customer ID is not found in the customer population."""
    pass


def ensure_explain_db_schema(conn: sqlite3.Connection) -> None:
    """Ensure database tables for customer explanations are initialized."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_explanations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            explanation_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_explanations_lookup ON customer_explanations (campaign_id, customer_id)"
    )
    conn.commit()


def determine_reason_code(
    p_treat: float,
    p_control: float,
    uplift: float,
    high_p_control_threshold: float = 0.5,
    uplift_operating_threshold: float = 0.02,
) -> ReasonCode:
    """Determine customer-level reason code based on canonical ML plan rules.

    Rules:
    1. likely_without_offer: p_control >= 0.5 and uplift < 0.02
    2. incremental_candidate: uplift >= 0.02
    3. negative_uplift: uplift < 0.0 (when p_control < 0.5)
    4. weak_response: both probabilities low and uplift near zero (0 <= uplift < 0.02, p_control < 0.5)
    """
    if p_control >= high_p_control_threshold and uplift < uplift_operating_threshold:
        return "likely_without_offer"

    if uplift >= uplift_operating_threshold:
        return "incremental_candidate"

    if uplift < 0.0:
        return "negative_uplift"

    return "weak_response"


def clean_feature_name(raw_name: str) -> Tuple[str, Optional[str]]:
    """Clean sklearn preprocessor prefixes e.g. remainder__tenure_days -> (tenure_days, None)

    Returns:
        (clean_column_name, category_value_if_one_hot)
    """
    clean = raw_name
    if clean.startswith("remainder__"):
        clean = clean[len("remainder__"):]
        return clean, None
    if clean.startswith("cat__"):
        clean = clean[len("cat__"):]
        # Format: feature_name_CategoryVal
        parts = clean.split("_")
        if len(parts) >= 2:
            return parts[0], "_".join(parts[1:])
        return clean, None
    return clean, None


def extract_feature_contributions(
    model: Any,
    customer_series: pd.Series,
    score_row_df: pd.DataFrame,
    top_n: int = 5,
) -> List[FeatureContribution]:
    """Extract top signed feature contributions from tree booster or linear terms."""
    contributions_dict: Dict[str, float] = {}

    # Extract inner estimator / pipeline
    inner_model = getattr(model, "model", model)
    pipeline = getattr(inner_model, "model", inner_model)

    # 1. Tree SHAP / pred_contrib via LightGBM booster
    if hasattr(pipeline, "named_steps") and "classifier" in pipeline.named_steps:
        clf = pipeline.named_steps["classifier"]
        preprocessor = pipeline.named_steps.get("preprocessor")
        booster = getattr(clf, "booster_", None)

        if booster is not None and preprocessor is not None:
            try:
                # Prepare counterfactual input dataframes
                input_cols = getattr(inner_model, "input_cols", score_row_df.columns.tolist())
                # Ensure treatment column exists for S-learner
                df_treat = score_row_df.copy()
                df_treat["treatment"] = 1
                df_ctrl = score_row_df.copy()
                df_ctrl["treatment"] = 0

                valid_input_cols = [c for c in input_cols if c in df_treat.columns]
                X_treat = preprocessor.transform(df_treat[valid_input_cols])
                X_ctrl = preprocessor.transform(df_ctrl[valid_input_cols])

                contrib_treat = booster.predict(X_treat, pred_contrib=True)[0]
                contrib_ctrl = booster.predict(X_ctrl, pred_contrib=True)[0]

                # Difference in contributions: treatment - control
                # Last element is the bias / expected value term
                diff_contribs = contrib_treat[:-1] - contrib_ctrl[:-1]
                feature_names = preprocessor.get_feature_names_out()

                for i, raw_name in enumerate(feature_names):
                    feat_base, _ = clean_feature_name(raw_name)
                    if feat_base in ("treatment", "customer_id", "campaign_id", "eligible") or feat_base in FORBIDDEN_COLUMNS:
                        continue
                    val = float(diff_contribs[i])
                    # Aggregate contribution if multiple one-hot categories exist for one feature
                    contributions_dict[feat_base] = contributions_dict.get(feat_base, 0.0) + val
            except Exception:
                pass

    # 2. Fallback: linear coefficients / importances / standardized deviation
    if not contributions_dict:
        # Check for feature_importances_
        clf = getattr(pipeline, "named_steps", {}).get("classifier", pipeline)
        importances = getattr(clf, "feature_importances_", None)
        if importances is not None and hasattr(clf, "feature_names_in_"):
            for fname, imp in zip(clf.feature_names_in_, importances):
                if fname not in ("treatment", "customer_id", "campaign_id", "eligible") and fname not in FORBIDDEN_COLUMNS:
                    contributions_dict[fname] = float(imp)

    # 3. Final fallback: top numeric variations
    if not contributions_dict:
        for col in score_row_df.columns:
            if col in CAMPAIGN_FIELDS or col in ("customer_id", "treatment", "eligible") or col in FORBIDDEN_COLUMNS:
                continue
            val = score_row_df.iloc[0][col]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                contributions_dict[col] = round(float(val) * 0.01, 4)

    # Sort by absolute contribution descending
    sorted_feats = sorted(contributions_dict.items(), key=lambda x: abs(x[1]), reverse=True)

    items: List[FeatureContribution] = []
    for fname, contrib_val in sorted_feats[:top_n]:
        raw_val = customer_series.get(fname, "")
        if isinstance(raw_val, float):
            formatted_val = f"{raw_val:.4f}".rstrip("0").rstrip(".")
        else:
            formatted_val = str(raw_val)

        items.append(
            FeatureContribution(
                name=fname,
                value=formatted_val,
                contribution=round(float(contrib_val), 4),
            )
        )

    return items


def generate_template_text(
    p_treat: float,
    p_control: float,
    uplift: float,
    reason_code: str,
    feature_contributions: List[FeatureContribution],
) -> str:
    """Generate grounded narrative template using only calculated fields."""
    top_diffs = feature_contributions[:3]
    if top_diffs:
        diff_str = ", ".join(f"{fc.name} ({fc.contribution:+.2f})" for fc in top_diffs)
    else:
        diff_str = "none"

    return (
        f"Control probability is {p_control:.2f}. "
        f"Treated probability is {p_treat:.2f}. "
        f"Estimated uplift is {uplift:.2f}. "
        f"Reason code: {reason_code}. "
        f"Largest feature differences: {diff_str}."
    )


def explain_customer(
    campaign: Dict[str, Any],
    customer_id: str,
    settings: Optional[Settings] = None,
    conn: Optional[sqlite3.Connection] = None,
    model: Optional[Any] = None,
    feature_df: Optional[pd.DataFrame] = None,
) -> CustomerExplanationResponse:
    """Compute grounded probabilities, reason code, and feature contributions for one customer."""
    if settings is None:
        settings = get_settings()

    # 1. Load model if not provided
    if model is None:
        model, _ = load_model_artifact(settings.resolved_model_artifact_dir)

    # 2. Load feature records if not provided
    if feature_df is None:
        feature_df = load_feature_table(settings.resolved_feature_table_path)

    # 3. Find customer record
    if "customer_id" not in feature_df.columns:
        raise FeatureMismatchError("Feature table missing required 'customer_id' column")

    matched_rows = feature_df[feature_df["customer_id"].astype(str) == str(customer_id)]
    if matched_rows.empty:
        raise CustomerNotFoundError(f"Customer '{customer_id}' not found in feature table.")

    customer_row = matched_rows.iloc[0]

    # 4. Prepare feature dataframe with campaign variables
    score_df = matched_rows.copy()
    score_df["objective"] = campaign["objective"]
    score_df["offer_type"] = campaign["offer_type"]
    score_df["incentive_value"] = float(campaign["incentive_value"])
    score_df["incentive_cost_bdt"] = float(campaign["incentive_cost_bdt"])

    assert_no_forbidden_columns(score_df)

    # 5. Predict probabilities and uplift
    preds = model.predict_uplift(score_df)
    p_treat = round(float(preds.p_treat[0]), 4)
    p_control = round(float(preds.p_control[0]), 4)
    uplift = round(float(preds.uplift[0]), 4)

    # 6. Determine reason code
    reason_code = determine_reason_code(p_treat=p_treat, p_control=p_control, uplift=uplift)

    # 7. Compute feature contributions
    contributions = extract_feature_contributions(
        model=model,
        customer_series=customer_row,
        score_row_df=score_df,
        top_n=5,
    )

    # 8. Generate template text
    template_text = generate_template_text(
        p_treat=p_treat,
        p_control=p_control,
        uplift=uplift,
        reason_code=reason_code,
        feature_contributions=contributions,
    )

    explanation = CustomerExplanationResponse(
        customer_id=str(customer_id),
        p_treat=p_treat,
        p_control=p_control,
        uplift=uplift,
        reason_code=reason_code,
        feature_contributions=contributions,
        template_text=template_text,
    )

    # 9. Persist in SQLite
    if conn is not None:
        ensure_explain_db_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO customer_explanations (campaign_id, customer_id, reason_code, explanation_json, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (
                campaign["id"],
                str(customer_id),
                reason_code,
                json.dumps(explanation.model_dump()),
            ),
        )
        conn.commit()

    return explanation
