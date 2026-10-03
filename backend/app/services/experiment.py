"""Experiment intelligence service for CampaignLift backend.

Canonical planning sources:
- planning/backend_plan.md
- planning/ml_plan.md
- tasks/assaduzzaman/20_experiment_intelligence_api.md
- backend/openapi.yaml
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.schemas import (
    ExperimentSliceItem,
    ExperimentSummaryResponse,
)
from backend.app.services.inference import (
    FORBIDDEN_COLUMNS,
    ForbiddenColumnError,
    assert_no_forbidden_columns,
)
from backend.app.settings import REPO_ROOT, Settings, get_settings

# Minimum support threshold: at least 30 treated AND 30 control
MIN_SUPPORT_DEFAULT: int = 30

# Canonical slice dimensions required by ML & responsible AI plan
CANONICAL_SLICE_DIMENSIONS: Tuple[str, ...] = (
    "region_code",
    "age_band",
    "kyc_level",
    "activity_band",
    "exposure_band",
)


class ExperimentDataNotReadyError(FileNotFoundError):
    """Raised when exposures or outcomes dataset files are missing."""
    pass


def ensure_experiment_db_schema(conn: sqlite3.Connection) -> None:
    """Ensure database tables for experiment summaries are initialized."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS experiment_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            run_id TEXT,
            split TEXT,
            summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_experiment_summaries_campaign_id ON experiment_summaries (campaign_id)"
    )
    conn.commit()


def derive_activity_band(cnt: Optional[int]) -> str:
    """Derive observed activity band from txn_count_30d: (0, 1-4, 5+)."""
    if cnt is None or cnt == 0:
        return "0"
    if cnt <= 4:
        return "1-4"
    return "5+"


def derive_exposure_band(cnt: Optional[int]) -> str:
    """Derive prior exposure band from campaign_exposures_prior_30d: (0, 1-2, 3+)."""
    if cnt is None or cnt == 0:
        return "0"
    if cnt <= 2:
        return "1-2"
    return "3+"


def compute_experiment_summary(
    campaign_id: str,
    exposures: List[Dict[str, Any]] | Dict[str, Dict[str, Any]],
    outcomes: List[Dict[str, Any]] | Dict[str, Dict[str, Any]],
    features: Optional[List[Dict[str, Any]] | Dict[str, Dict[str, Any]]] = None,
    splits: Optional[List[Dict[str, Any]] | Dict[str, str]] = None,
    split_filter: Optional[str] = "test",
    run_id: Optional[str] = None,
    min_support: int = MIN_SUPPORT_DEFAULT,
) -> ExperimentSummaryResponse:
    """Compute deterministic treatment vs control summary and slices from factual rows.

    Args:
        campaign_id: Unique campaign identifier.
        exposures: List or dict of exposures containing customer_id and treatment (0 or 1).
        outcomes: List or dict of factual outcomes containing customer_id and y_transacted (0 or 1).
        features: Optional customer features for slicing.
        splits: Optional split mapping e.g. train, val, test.
        split_filter: Split to evaluate on e.g. 'test', 'fixture', 'all'. If None or not found, uses available candidates.
        run_id: Associated run identifier.
        min_support: Minimum sample size required in each arm for sufficient support (default: 30).

    Returns:
        ExperimentSummaryResponse with arm sizes, rates, incremental outcome, and slice details.
    """
    # 1. Normalize exposures: customer_id -> int(treatment)
    treatments_map: Dict[str, int] = {}
    if isinstance(exposures, list):
        for e in exposures:
            cid = str(e["customer_id"])
            treatments_map[cid] = int(e.get("treatment", 0))
    elif isinstance(exposures, dict):
        for cid, val in exposures.items():
            if isinstance(val, dict):
                treatments_map[str(cid)] = int(val.get("treatment", 0))
            else:
                treatments_map[str(cid)] = int(val)

    # 2. Normalize outcomes: customer_id -> int(y_transacted)
    outcomes_map: Dict[str, int] = {}
    if isinstance(outcomes, list):
        for o in outcomes:
            cid = str(o["customer_id"])
            outcomes_map[cid] = int(o.get("y_transacted", 0))
    elif isinstance(outcomes, dict):
        for cid, val in outcomes.items():
            if isinstance(val, dict):
                outcomes_map[str(cid)] = int(val.get("y_transacted", 0))
            else:
                outcomes_map[str(cid)] = int(val)

    # 3. Normalize splits: customer_id -> str(split)
    splits_map: Dict[str, str] = {}
    if splits is not None:
        if isinstance(splits, list):
            for s in splits:
                cid = str(s["customer_id"])
                splits_map[cid] = str(s.get("split", "")).lower()
        elif isinstance(splits, dict):
            for cid, sval in splits.items():
                if isinstance(sval, dict):
                    splits_map[str(cid)] = str(sval.get("split", "")).lower()
                else:
                    splits_map[str(cid)] = str(sval).lower()

    # 4. Normalize features: customer_id -> dict
    features_map: Dict[str, Dict[str, Any]] = {}
    if features is not None:
        if isinstance(features, list):
            for f in features:
                assert_no_forbidden_columns(f)
                features_map[str(f["customer_id"])] = f
        elif isinstance(features, dict):
            for cid, f in features.items():
                assert_no_forbidden_columns(f)
                features_map[str(cid)] = f

    # 5. Overlap of customers who have both treatment exposure and outcome
    overlap_cids = [cid for cid in treatments_map if cid in outcomes_map]
    if not overlap_cids:
        raise ValueError("No customers found with both exposure and outcome records.")

    # Apply split filter if requested
    target_cids = overlap_cids
    if split_filter and split_filter.lower() not in ("all", "fixture", "none"):
        split_matched = [cid for cid in overlap_cids if splits_map.get(cid) == split_filter.lower()]
        if split_matched:
            target_cids = split_matched

    # 6. Treatment vs Control arm separation
    treated_cids = [cid for cid in target_cids if treatments_map[cid] == 1]
    control_cids = [cid for cid in target_cids if treatments_map[cid] == 0]

    total_treated = len(treated_cids)
    total_control = len(control_cids)

    if total_treated == 0 or total_control == 0:
        raise ValueError(
            f"Both treatment and control arms must be present. Found treated={total_treated}, control={total_control}."
        )

    # 7. Arm outcome calculations
    treated_successes = sum(outcomes_map[cid] for cid in treated_cids)
    control_successes = sum(outcomes_map[cid] for cid in control_cids)

    treated_outcome_rate = round(treated_successes / total_treated, 4)
    control_outcome_rate = round(control_successes / total_control, 4)
    overall_incremental_outcome = round(treated_outcome_rate - control_outcome_rate, 4)

    # 8. Slice-level calculations
    # Detect candidate slice columns
    slice_data: Dict[Tuple[str, str], Dict[str, int]] = {}

    for cid in target_cids:
        arm = treatments_map[cid]
        y = outcomes_map[cid]
        feat = features_map.get(cid, {})

        # Extract values for canonical slices
        slice_vals: Dict[str, str] = {}

        if "region_code" in feat:
            slice_vals["region_code"] = str(feat["region_code"])
        if "age_band" in feat:
            slice_vals["age_band"] = str(feat["age_band"])
        if "kyc_level" in feat:
            slice_vals["kyc_level"] = str(feat["kyc_level"])

        # Activity band
        if "activity_band" in feat:
            slice_vals["activity_band"] = str(feat["activity_band"])
        elif "txn_count_30d" in feat:
            slice_vals["activity_band"] = derive_activity_band(feat.get("txn_count_30d"))

        # Exposure band
        if "exposure_band" in feat:
            slice_vals["exposure_band"] = str(feat["exposure_band"])
        elif "campaign_exposures_prior_30d" in feat:
            slice_vals["exposure_band"] = derive_exposure_band(feat.get("campaign_exposures_prior_30d"))

        # Check for any extra custom categorical features provided (e.g. in test fixtures)
        for k, v in feat.items():
            if k in ("customer_id", "campaign_id", "eligible") or k in slice_vals or k in FORBIDDEN_COLUMNS:
                continue
            if isinstance(v, (str, bool)):
                slice_vals[k] = str(v)

        for s_name, s_val in slice_vals.items():
            key = (s_name, s_val)
            if key not in slice_data:
                slice_data[key] = {
                    "treated_count": 0,
                    "control_count": 0,
                    "treated_successes": 0,
                    "control_successes": 0,
                }
            if arm == 1:
                slice_data[key]["treated_count"] += 1
                slice_data[key]["treated_successes"] += y
            else:
                slice_data[key]["control_count"] += 1
                slice_data[key]["control_successes"] += y

    # Assemble slice items applying the support rule
    slice_items: List[ExperimentSliceItem] = []
    for (s_name, s_val), counts in sorted(slice_data.items(), key=lambda x: (x[0][0], x[0][1])):
        t_cnt = counts["treated_count"]
        c_cnt = counts["control_count"]

        # Support rule: must have at least min_support treated AND min_support control
        if t_cnt >= min_support and c_cnt >= min_support:
            support = "sufficient"
            t_rate = round(counts["treated_successes"] / t_cnt, 4)
            c_rate = round(counts["control_successes"] / c_cnt, 4)
            inc = round(t_rate - c_rate, 4)
        else:
            support = "insufficient"
            t_rate = None
            c_rate = None
            inc = None

        slice_items.append(
            ExperimentSliceItem(
                slice_name=s_name,
                slice_value=s_val,
                treated_count=t_cnt,
                control_count=c_cnt,
                support=support,
                treated_outcome_rate=t_rate,
                control_outcome_rate=c_rate,
                incremental_outcome=inc,
            )
        )

    return ExperimentSummaryResponse(
        campaign_id=campaign_id,
        run_id=run_id,
        total_treated=total_treated,
        total_control=total_control,
        treated_outcome_rate=treated_outcome_rate,
        control_outcome_rate=control_outcome_rate,
        overall_incremental_outcome=overall_incremental_outcome,
        slices=slice_items,
    )


def get_or_create_experiment_summary(
    campaign_id: str,
    split: Optional[str] = None,
    settings: Optional[Settings] = None,
    conn: Optional[sqlite3.Connection] = None,
    fixture_dir: Optional[Path] = None,
    min_support: int = MIN_SUPPORT_DEFAULT,
) -> ExperimentSummaryResponse:
    """Retrieve or compute treatment vs control experiment summary from factual dataset files."""
    if settings is None:
        settings = get_settings()

    if fixture_dir is None:
        fixture_dir = settings.resolved_feature_table_path.parent
        if not fixture_dir.exists():
            fixture_dir = REPO_ROOT / "data" / "fixtures" / "fixture_v1"

    exposures_file = fixture_dir / "exposures.json"
    outcomes_file = fixture_dir / "outcomes.json"

    if not exposures_file.is_file() or not outcomes_file.is_file():
        raise ExperimentDataNotReadyError(
            f"Required experiment files (exposures.json or outcomes.json) missing in {fixture_dir}"
        )

    with open(exposures_file, "r", encoding="utf-8") as f:
        exposures_data = json.load(f)

    with open(outcomes_file, "r", encoding="utf-8") as f:
        outcomes_data = json.load(f)

    features_file = fixture_dir / "features.json"
    features_data = None
    if features_file.is_file():
        with open(features_file, "r", encoding="utf-8") as f:
            features_data = json.load(f)

    splits_file = fixture_dir / "splits.json"
    splits_data = None
    if splits_file.is_file():
        with open(splits_file, "r", encoding="utf-8") as f:
            splits_data = json.load(f)

    # Determine run_id if score runs exist
    run_id: Optional[str] = None
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT run_id FROM score_runs WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 1",
                (campaign_id,),
            )
            r_row = cursor.fetchone()
            if r_row:
                run_id = r_row["run_id"]
        except Exception:
            pass

    if run_id is None:
        run_id = f"exp_{campaign_id}_{int(time.time())}"

    # Target split: if user specifies split, use it. Otherwise, default to "test" if test split is present, else None
    effective_split = split
    if effective_split is None and splits_data:
        has_test = any(s.get("split") == "test" for s in splits_data if isinstance(s, dict))
        if has_test:
            effective_split = "test"

    summary = compute_experiment_summary(
        campaign_id=campaign_id,
        exposures=exposures_data,
        outcomes=outcomes_data,
        features=features_data,
        splits=splits_data,
        split_filter=effective_split,
        run_id=run_id,
        min_support=min_support,
    )

    # Persist in SQLite
    if conn is not None:
        ensure_experiment_db_schema(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO experiment_summaries (campaign_id, run_id, split, summary_json, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (
                campaign_id,
                summary.run_id,
                effective_split,
                json.dumps(summary.model_dump()),
            ),
        )
        conn.commit()

    return summary
