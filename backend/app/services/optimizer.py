"""Budget optimizer service implementing greedy knapsack allocation and strategy comparison.

Canonical planning sources:
- planning/optimizer_plan.md
- planning/backend_plan.md
- backend/openapi.yaml
- tasks/assaduzzaman/19_budget_optimizer_api.md
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.schemas import (
    OptimizeRequest,
    OptimizeResponse,
    StrategyComparisonResponse,
    StrategyMetricItem,
)
from backend.app.settings import REPO_ROOT, Settings, get_settings


def ensure_optimizer_db_schema(conn: sqlite3.Connection) -> None:
    """Initialize database tables for allocation and strategy comparisons."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            run_id TEXT,
            strategy TEXT NOT NULL,
            selected_count INTEGER NOT NULL,
            budget_bdt REAL NOT NULL,
            spend_bdt REAL NOT NULL,
            expected_incremental_value REAL NOT NULL,
            support TEXT NOT NULL,
            measured_incremental_response REAL,
            cost_per_incremental_txn_bdt REAL,
            negative_uplift_selected_share REAL NOT NULL,
            selected_customer_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            run_id TEXT,
            evaluation_split TEXT NOT NULL,
            comparison_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_allocations_campaign_id ON allocations (campaign_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_strategy_comparisons_campaign_id ON strategy_comparisons (campaign_id)"
    )
    conn.commit()


def load_test_exposures_and_outcomes(
    fixture_dir: Optional[Path] = None,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Load factual test/fixture treatment assignment and outcomes if available.

    Returns:
        (treatments_by_id, outcomes_by_id)
    """
    if fixture_dir is None:
        fixture_dir = REPO_ROOT / "data" / "fixtures" / "fixture_v1"

    treatments: Dict[str, int] = {}
    outcomes: Dict[str, int] = {}

    exposures_file = fixture_dir / "exposures.json"
    if exposures_file.is_file():
        try:
            with open(exposures_file, "r", encoding="utf-8") as f:
                exp_data = json.load(f)
            for row in exp_data:
                treatments[str(row["customer_id"])] = int(row.get("treatment", 0))
        except Exception:
            pass

    outcomes_file = fixture_dir / "outcomes.json"
    if outcomes_file.is_file():
        try:
            with open(outcomes_file, "r", encoding="utf-8") as f:
                out_data = json.load(f)
            for row in out_data:
                outcomes[str(row["customer_id"])] = int(row.get("y_transacted", 0))
        except Exception:
            pass

    return treatments, outcomes


def evaluate_test_slice(
    selected_ids: List[str],
    spend_bdt: float,
    treatments: Dict[str, int],
    outcomes: Dict[str, int],
) -> Tuple[str, Optional[float], Optional[float]]:
    """Compute measured factual incremental response on test-split overlap.

    Returns:
        (support, measured_incremental_response, cost_per_incremental_txn_bdt)
    """
    # Overlap with test split
    treated_outcomes: List[int] = []
    control_outcomes: List[int] = []

    for cid in selected_ids:
        if cid in treatments and cid in outcomes:
            arm = treatments[cid]
            y = outcomes[cid]
            if arm == 1:
                treated_outcomes.append(y)
            else:
                control_outcomes.append(y)

    # Minimum support rule (at least 5 in each arm)
    if len(treated_outcomes) < 5 or len(control_outcomes) < 5:
        return "insufficient", None, None

    mean_treat = float(sum(treated_outcomes) / len(treated_outcomes))
    mean_control = float(sum(control_outcomes) / len(control_outcomes))
    incremental_rate = round(mean_treat - mean_control, 4)

    # Cost per incremental transaction
    cost_per_incremental: Optional[float] = None
    if incremental_rate > 0 and len(selected_ids) > 0:
        expected_inc_txns = incremental_rate * len(selected_ids)
        if expected_inc_txns > 0:
            cost_per_incremental = round(spend_bdt / expected_inc_txns, 2)

    return "sufficient", incremental_rate, cost_per_incremental


def optimize_campaign_budget(
    campaign: Dict[str, Any],
    scored_customers: List[Dict[str, Any]],
    request: Optional[OptimizeRequest] = None,
    conn: Optional[sqlite3.Connection] = None,
    fixture_dir: Optional[Path] = None,
) -> OptimizeResponse:
    """Execute greedy budget allocation for uplift, response, and random strategies."""
    if request is None:
        request = OptimizeRequest()

    # Budget & Cost constraints
    budget_bdt = float(
        request.budget_bdt if request.budget_bdt is not None else campaign["budget_bdt"]
    )
    if budget_bdt <= 0:
        raise ValueError("Budget must be strictly positive.")

    unit_cost_bdt = float(campaign["incentive_cost_bdt"])
    if unit_cost_bdt < 0:
        raise ValueError("Incentive cost per customer must be non-negative.")

    # Filter eligible customers only
    eligible_customers = [c for c in scored_customers if bool(c.get("eligible", True))]
    if not eligible_customers:
        raise ValueError("No eligible customers found to allocate budget.")

    # Check for duplicate customer IDs
    seen_ids = set()
    for c in eligible_customers:
        cid = c["customer_id"]
        if cid in seen_ids:
            raise ValueError(f"Duplicate customer ID detected in population: {cid}")
        seen_ids.add(cid)

    # Count customers with negative uplift
    neg_uplift_count = sum(1 for c in eligible_customers if float(c["uplift"]) < 0)

    # Assumed unit value per incremental transaction
    assumed_value = request.value_per_incremental_transaction_bdt
    if assumed_value is not None and assumed_value <= 0:
        assumed_value = None  # Zero value treated as not provided

    # -------------------------------------------------------------------------
    # 1. Strategy: Uplift
    # -------------------------------------------------------------------------
    uplift_candidates = list(eligible_customers)
    if request.exclude_negative_uplift:
        uplift_candidates = [c for c in uplift_candidates if float(c["uplift"]) >= 0]

    if assumed_value is not None:
        # Rank by net value: (uplift * value) - unit_cost
        def uplift_key(c: Dict[str, Any]) -> Tuple[float, float, str]:
            uplift_val = float(c["uplift"])
            net_val = (uplift_val * assumed_value) - unit_cost_bdt
            return (net_val, uplift_val, c["customer_id"])

        # Skip rows with negative net value
        uplift_candidates = [
            c for c in uplift_candidates
            if ((float(c["uplift"]) * assumed_value) - unit_cost_bdt) >= 0
        ]
        # Sort descending by net_val, tie-break uplift descending, customer_id ascending
        uplift_candidates.sort(key=lambda c: (-uplift_key(c)[0], -uplift_key(c)[1], c["customer_id"]))
    else:
        # Rank strictly by predicted uplift descending, tie-break p_treat descending, customer_id ascending
        uplift_candidates.sort(
            key=lambda c: (-float(c["uplift"]), -float(c["p_treat"]), c["customer_id"])
        )

    # Greedy knapsack selection under budget
    selected_uplift: List[Dict[str, Any]] = []
    current_spend_uplift = 0.0

    if unit_cost_bdt > 0:
        for c in uplift_candidates:
            if current_spend_uplift + unit_cost_bdt <= budget_bdt:
                if request.max_customers is None or len(selected_uplift) < request.max_customers:
                    selected_uplift.append(c)
                    current_spend_uplift += unit_cost_bdt
                else:
                    break
            else:
                break
    else:
        # Zero cost offer: allocate up to max_customers
        cap = request.max_customers or len(uplift_candidates)
        selected_uplift = uplift_candidates[:cap]

    # Calculate expected incremental value (sum of predicted uplifts, NEVER multiplied by fake ROI)
    expected_inc_val_uplift = round(sum(float(c["uplift"]) for c in selected_uplift), 4)

    # -------------------------------------------------------------------------
    # 2. Strategy: Response Baseline (p_treat descending)
    # Does NOT exclude negative uplift
    # -------------------------------------------------------------------------
    response_candidates = list(eligible_customers)
    response_candidates.sort(
        key=lambda c: (-float(c["p_treat"]), -float(c["uplift"]), c["customer_id"])
    )

    selected_response: List[Dict[str, Any]] = []
    current_spend_response = 0.0

    if unit_cost_bdt > 0:
        for c in response_candidates:
            if current_spend_response + unit_cost_bdt <= budget_bdt:
                if request.max_customers is None or len(selected_response) < request.max_customers:
                    selected_response.append(c)
                    current_spend_response += unit_cost_bdt
                else:
                    break
            else:
                break
    else:
        cap = request.max_customers or len(response_candidates)
        selected_response = response_candidates[:cap]

    expected_inc_val_response = round(sum(float(c["uplift"]) for c in selected_response), 4)

    # -------------------------------------------------------------------------
    # 3. Strategy: Random Allocation
    # Does NOT exclude negative uplift; deterministic seeded shuffle
    # -------------------------------------------------------------------------
    random_candidates = list(eligible_customers)
    camp_hash = int(hashlib.sha256(str(campaign["id"]).encode("utf-8")).hexdigest(), 16)
    rng = random.Random(20261006 + (camp_hash % 1000000))
    rng.shuffle(random_candidates)

    selected_random: List[Dict[str, Any]] = []
    current_spend_random = 0.0

    if unit_cost_bdt > 0:
        for c in random_candidates:
            if current_spend_random + unit_cost_bdt <= budget_bdt:
                if request.max_customers is None or len(selected_random) < request.max_customers:
                    selected_random.append(c)
                    current_spend_random += unit_cost_bdt
                else:
                    break
            else:
                break
    else:
        cap = request.max_customers or len(random_candidates)
        selected_random = random_candidates[:cap]

    expected_inc_val_random = round(sum(float(c["uplift"]) for c in selected_random), 4)

    # -------------------------------------------------------------------------
    # Evaluation on Factual Test Outcomes
    # -------------------------------------------------------------------------
    treatments, outcomes = load_test_exposures_and_outcomes(fixture_dir)

    def build_metric_item(
        strat_name: str,
        selected: List[Dict[str, Any]],
        spend: float,
        exp_val: float,
    ) -> StrategyMetricItem:
        cids = [c["customer_id"] for c in selected]
        n_sel = len(cids)
        neg_share = (
            round(sum(1 for c in selected if float(c["uplift"]) < 0) / n_sel, 4)
            if n_sel > 0
            else 0.0
        )
        supp, inc_rate, cost_per_inc = evaluate_test_slice(
            cids, spend, treatments, outcomes
        )
        return StrategyMetricItem(
            strategy=strat_name,  # type: ignore
            selected_count=n_sel,
            spend_bdt=round(spend, 2),
            expected_incremental_value=exp_val,
            support=supp,  # type: ignore
            measured_incremental_response=inc_rate,
            cost_per_incremental_txn_bdt=cost_per_inc,
            negative_uplift_selected_share=neg_share,
        )

    uplift_item = build_metric_item(
        "uplift", selected_uplift, current_spend_uplift, expected_inc_val_uplift
    )
    response_item = build_metric_item(
        "response", selected_response, current_spend_response, expected_inc_val_response
    )
    random_item = build_metric_item(
        "random", selected_random, current_spend_random, expected_inc_val_random
    )

    comparison_response = StrategyComparisonResponse(
        campaign_id=campaign["id"],
        run_id=scored_customers[0].get("run_id") if scored_customers else None,
        evaluation_split="fixture",
        strategies=[random_item, response_item, uplift_item],
    )

    # -------------------------------------------------------------------------
    # Database Persistence
    # -------------------------------------------------------------------------
    if conn is not None:
        ensure_optimizer_db_schema(conn)
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cursor = conn.cursor()

        # Save individual strategy allocations
        for strat_item, sel_list in [
            (uplift_item, selected_uplift),
            (response_item, selected_response),
            (random_item, selected_random),
        ]:
            cursor.execute(
                """
                INSERT INTO allocations (
                    campaign_id, run_id, strategy, selected_count, budget_bdt, spend_bdt,
                    expected_incremental_value, support, measured_incremental_response,
                    cost_per_incremental_txn_bdt, negative_uplift_selected_share,
                    selected_customer_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign["id"],
                    comparison_response.run_id,
                    strat_item.strategy,
                    strat_item.selected_count,
                    budget_bdt,
                    strat_item.spend_bdt,
                    strat_item.expected_incremental_value,
                    strat_item.support,
                    strat_item.measured_incremental_response,
                    strat_item.cost_per_incremental_txn_bdt,
                    strat_item.negative_uplift_selected_share,
                    json.dumps([c["customer_id"] for c in sel_list]),
                    created_at,
                ),
            )

        # Save strategy comparison record
        cursor.execute(
            """
            INSERT INTO strategy_comparisons (
                campaign_id, run_id, evaluation_split, comparison_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                campaign["id"],
                comparison_response.run_id,
                comparison_response.evaluation_split,
                comparison_response.model_dump_json(),
                created_at,
            ),
        )
        conn.commit()

    return OptimizeResponse(
        strategy="uplift",
        selected_count=len(selected_uplift),
        budget_bdt=budget_bdt,
        spend_bdt=round(current_spend_uplift, 2),
        expected_incremental_value=expected_inc_val_uplift,
        customers_excluded_negative=neg_uplift_count if request.exclude_negative_uplift else 0,
        selected_customer_ids=[c["customer_id"] for c in selected_uplift],
        comparison=comparison_response,
    )
