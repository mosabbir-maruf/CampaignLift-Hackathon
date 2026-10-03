"""Inference service for CampaignLift uplift scoring.

Canonical planning sources:
- planning/backend_plan.md
- planning/ml_plan.md
- backend/openapi.yaml
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import joblib
import numpy as np
import pandas as pd

from backend.app.schemas import (
    CustomerScoreItem,
    ScoreRunResponse,
    UpliftDecile,
)
from backend.app.settings import REPO_ROOT, Settings, get_settings

# Ensure ML package is importable for deserializing model estimators
ml_src_path = str(REPO_ROOT / "ml" / "src")
if ml_src_path not in sys.path:
    sys.path.insert(0, ml_src_path)

# Canonical forbidden causal leakage columns
FORBIDDEN_COLUMNS: Set[str] = {
    "natural_transaction_propensity",
    "qr_affinity",
    "price_sensitivity",
    "campaign_sensitivity",
    "digital_maturity",
    "offer_fatigue",
    "p_y_control",
    "p_y_treat",
    "true_uplift",
}

# Campaign-level dynamic columns provided at inference time
CAMPAIGN_FIELDS: Set[str] = {
    "objective",
    "offer_type",
    "incentive_value",
    "incentive_cost_bdt",
}


class ForbiddenColumnError(ValueError):
    """Raised when an unobservable latent or oracle ground-truth column is detected."""
    pass


class FeatureMismatchError(ValueError):
    """Raised when the loaded feature table lacks columns required by the model."""
    pass


class ModelNotReadyError(FileNotFoundError):
    """Raised when the model artifact directory or binary is missing."""
    pass


class FeatureTableNotReadyError(FileNotFoundError):
    """Raised when the customer feature table is missing or unreadable."""
    pass


def assert_no_forbidden_columns(cols: Any) -> None:
    """Validate that candidate columns contain zero forbidden causal variables."""
    if isinstance(cols, pd.DataFrame):
        candidate_cols = set(cols.columns)
    elif isinstance(cols, dict):
        candidate_cols = set(cols.keys())
    elif isinstance(cols, (list, tuple, set)):
        if cols and isinstance(cols[0], dict):
            candidate_cols = set(cols[0].keys())
        else:
            candidate_cols = set(cols)
    else:
        return

    leaked = candidate_cols.intersection(FORBIDDEN_COLUMNS)
    if leaked:
        raise ForbiddenColumnError(
            f"CRITICAL CAUSAL LEAKAGE: Forbidden ground truth column detected: {sorted(list(leaked))}"
        )


def ensure_db_schema(conn: sqlite3.Connection) -> None:
    """Ensure database tables for campaigns and scores are initialized."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            objective TEXT NOT NULL,
            offer_type TEXT NOT NULL,
            incentive_value REAL NOT NULL,
            incentive_cost_bdt REAL NOT NULL,
            budget_bdt REAL NOT NULL,
            channel TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS score_runs (
            run_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            total_eligible INTEGER NOT NULL,
            total_scored INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            eligible INTEGER NOT NULL,
            p_treat REAL NOT NULL,
            p_control REAL NOT NULL,
            uplift REAL NOT NULL,
            response_rank INTEGER NOT NULL,
            uplift_rank INTEGER NOT NULL,
            FOREIGN KEY (run_id) REFERENCES score_runs (run_id),
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_scores_run_id ON customer_scores (run_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_scores_campaign_id ON customer_scores (campaign_id)"
    )
    conn.commit()


def load_model_artifact(artifact_dir: Path) -> Tuple[Any, Dict[str, Any]]:
    """Load serialized model binary and metadata JSON from artifact directory."""
    if not artifact_dir.is_dir():
        raise ModelNotReadyError(f"Model artifact directory not found at: {artifact_dir}")

    metadata_path = artifact_dir / "metadata.json"
    if not metadata_path.is_file():
        raise ModelNotReadyError(f"Missing metadata.json in artifact directory: {artifact_dir}")

    binary_path = artifact_dir / "model.joblib"
    if not binary_path.is_file():
        raise ModelNotReadyError(f"Missing model binary model.joblib in artifact directory: {artifact_dir}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    model = joblib.load(binary_path)
    return model, metadata


def load_feature_table(feature_table_path: Path) -> pd.DataFrame:
    """Load customer feature records from disk (JSON or Parquet)."""
    if not feature_table_path.is_file():
        raise FeatureTableNotReadyError(f"Feature table file not found at: {feature_table_path}")

    try:
        if feature_table_path.suffix == ".parquet":
            df = pd.read_parquet(feature_table_path)
        else:
            with open(feature_table_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
    except Exception as exc:
        raise FeatureTableNotReadyError(f"Failed to read feature table: {str(exc)}")

    assert_no_forbidden_columns(df)
    return df


def compute_uplift_deciles(scores: List[Dict[str, Any]]) -> List[UpliftDecile]:
    """Compute 10 summary deciles from customers sorted by uplift descending."""
    n = len(scores)
    if n == 0:
        return []

    # Sort strictly by uplift descending
    sorted_scores = sorted(scores, key=lambda x: x["uplift"], reverse=True)
    deciles: List[UpliftDecile] = []

    # 10 equal bins
    for d in range(1, 11):
        start_idx = int((d - 1) * n / 10)
        end_idx = int(d * n / 10)
        bucket = sorted_scores[start_idx:end_idx]

        if not bucket:
            continue

        bucket_uplifts = [row["uplift"] for row in bucket]
        deciles.append(
            UpliftDecile(
                decile=d,
                customer_count=len(bucket),
                mean_uplift=round(float(np.mean(bucket_uplifts)), 6),
                min_uplift=round(float(np.min(bucket_uplifts)), 6),
                max_uplift=round(float(np.max(bucket_uplifts)), 6),
            )
        )

    return deciles


def score_campaign_population(
    campaign: Dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    settings: Optional[Settings] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> ScoreRunResponse:
    """Execute uplift scoring for all eligible customers under the given campaign definition."""
    if settings is None:
        settings = get_settings()

    # 1. Load model and metadata
    model, metadata = load_model_artifact(settings.resolved_model_artifact_dir)
    model_version = metadata.get("model_version", "unknown")
    dataset_version = metadata.get("dataset_version", settings.dataset_version)
    expected_features = metadata.get("feature_names", [])

    # 2. Load feature records
    feature_df = load_feature_table(settings.resolved_feature_table_path)

    # 3. Check for customer_id and required feature columns
    if "customer_id" not in feature_df.columns:
        raise FeatureMismatchError("Feature table missing required 'customer_id' column")

    customer_required_cols = [c for c in expected_features if c not in CAMPAIGN_FIELDS]
    missing_cols = [c for c in customer_required_cols if c not in feature_df.columns]
    if missing_cols:
        raise FeatureMismatchError(
            f"Feature table schema mismatch. Missing required columns: {sorted(missing_cols)}"
        )

    # 4. Prepare feature dataframe with campaign variables
    score_df = feature_df.copy()
    score_df["objective"] = campaign["objective"]
    score_df["offer_type"] = campaign["offer_type"]
    score_df["incentive_value"] = float(campaign["incentive_value"])
    score_df["incentive_cost_bdt"] = float(campaign["incentive_cost_bdt"])

    # Enforce anti-leakage boundary on inference input
    assert_no_forbidden_columns(score_df)

    # 5. Execute model inference
    preds = model.predict_uplift(score_df)

    p_treat = np.asarray(preds.p_treat, dtype=float)
    p_control = np.asarray(preds.p_control, dtype=float)
    uplift = np.asarray(preds.uplift, dtype=float)

    # Verify predictions are finite real numbers
    if not (np.all(np.isfinite(p_treat)) and np.all(np.isfinite(p_control)) and np.all(np.isfinite(uplift))):
        raise ValueError("Model inference produced non-finite probability or uplift values.")

    n_customers = len(score_df)
    customer_ids = score_df["customer_id"].astype(str).tolist()
    eligible_flags = [bool(x) for x in score_df.get("eligible", [True] * n_customers)]

    # 6. Rank assignment
    # Uplift rank (1 = highest uplift)
    uplift_order = np.argsort(-uplift)
    uplift_ranks = np.empty(n_customers, dtype=int)
    uplift_ranks[uplift_order] = np.arange(1, n_customers + 1)

    # Response rank (1 = highest p_treat)
    response_order = np.argsort(-p_treat)
    response_ranks = np.empty(n_customers, dtype=int)
    response_ranks[response_order] = np.arange(1, n_customers + 1)

    # 7. Build full scored customer records
    all_scored_items: List[Dict[str, Any]] = []
    for i in range(n_customers):
        all_scored_items.append(
            {
                "customer_id": customer_ids[i],
                "eligible": eligible_flags[i],
                "p_treat": round(float(p_treat[i]), 6),
                "p_control": round(float(p_control[i]), 6),
                "uplift": round(float(uplift[i]), 6),
                "response_rank": int(response_ranks[i]),
                "uplift_rank": int(uplift_ranks[i]),
            }
        )

    # Anti-leakage: verify no forbidden field was injected
    assert_no_forbidden_columns(all_scored_items)

    # Compute uplift deciles across all scored customers
    deciles = compute_uplift_deciles(all_scored_items)

    # 8. Persist score run and customer records in SQLite
    run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if conn is not None:
        ensure_db_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO score_runs (run_id, campaign_id, model_version, dataset_version, total_eligible, total_scored, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                campaign["id"],
                model_version,
                dataset_version,
                n_customers,
                n_customers,
                created_at,
            ),
        )

        # Batch insert scores
        rows_to_insert = [
            (
                run_id,
                campaign["id"],
                item["customer_id"],
                1 if item["eligible"] else 0,
                item["p_treat"],
                item["p_control"],
                item["uplift"],
                item["response_rank"],
                item["uplift_rank"],
            )
            for item in all_scored_items
        ]
        cursor.executemany(
            """
            INSERT INTO customer_scores (
                run_id, campaign_id, customer_id, eligible, p_treat, p_control, uplift, response_rank, uplift_rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()

    # Sort paginated items by uplift_rank ascending
    all_scored_items.sort(key=lambda x: x["uplift_rank"])
    paginated_items = all_scored_items[offset : offset + limit]

    return ScoreRunResponse(
        run_id=run_id,
        campaign_id=campaign["id"],
        model_version=model_version,
        dataset_version=dataset_version,
        total_eligible=n_customers,
        total_scored=n_customers,
        uplift_deciles=deciles,
        items=[CustomerScoreItem(**item) for item in paginated_items],
        limit=limit,
        offset=offset,
        total_count=n_customers,
    )
