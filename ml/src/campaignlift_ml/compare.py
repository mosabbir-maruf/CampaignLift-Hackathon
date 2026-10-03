"""Strategy Comparison Calculator for CampaignLift.

Compares three customer targeting strategies on validation or test cohorts under a fixed budget:
1. 'random': Seeded random shuffle (baseline).
2. 'response': Ranked by response propensity p_treat descending (traditional targeting).
3. 'uplift': Ranked by predicted causal uplift descending (CampaignLift targeting).

Core Constraints:
- Budget must be strictly respected (total spend <= budget_bdt).
- Same budget and cost inputs applied identically to all three strategies.
- Random selection uses documented seed (default: 20261006).
- Measured incremental metrics use factual outcomes (y_transacted) only.
- Strict separation of 'expected_from_scores' vs 'measured' blocks.
- Cost per incremental transaction is reported only when measured incremental transactions > 0.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from .data import TARGET_COLUMN, TREATMENT_COLUMN, load_train_val
from .metrics import compute_incremental_response, compute_treatment_rate


DEFAULT_BUDGET_BDT: float = 100.0
DEFAULT_COST_PER_CUSTOMER_BDT: float = 10.0
DEFAULT_RANDOM_SEED: int = 20261006


@dataclass
class StrategyEvaluation:
    """Evaluation metrics for a single targeting strategy under a fixed budget."""
    strategy_name: str
    budget_bdt: float
    cost_per_customer_bdt: float
    total_spend_bdt: float
    budget_respected: bool
    selected_count: int
    selected_indices: List[int]
    selected_customer_ids: List[Any]
    expected_from_scores: Dict[str, Any]
    measured: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy evaluation to JSON-serializable dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "budget_bdt": self.budget_bdt,
            "cost_per_customer_bdt": self.cost_per_customer_bdt,
            "total_spend_bdt": self.total_spend_bdt,
            "budget_respected": self.budget_respected,
            "selected_count": self.selected_count,
            "selected_customer_ids": self.selected_customer_ids[:20],  # truncate if long
            "expected_from_scores": self.expected_from_scores,
            "measured": self.measured,
        }


@dataclass
class StrategyComparisonResult:
    """Full comparative evaluation across random, response, and uplift strategies."""
    budget_bdt: float
    cost_per_customer_bdt: float
    total_available_customers: int
    max_selectable_customers: int
    random: StrategyEvaluation
    response: StrategyEvaluation
    uplift: StrategyEvaluation
    selections_identical: bool
    identical_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert full comparison to dictionary."""
        return {
            "budget_bdt": self.budget_bdt,
            "cost_per_customer_bdt": self.cost_per_customer_bdt,
            "total_available_customers": self.total_available_customers,
            "max_selectable_customers": self.max_selectable_customers,
            "selections_identical": self.selections_identical,
            "identical_reason": self.identical_reason,
            "strategies": {
                "random": self.random.to_dict(),
                "response": self.response.to_dict(),
                "uplift": self.uplift.to_dict(),
            },
        }


def _evaluate_selected_cohort(
    selected_df: pd.DataFrame,
    strategy_name: str,
    budget_bdt: float,
    cost_per_customer_bdt: float,
    has_customer_id: bool = True,
) -> StrategyEvaluation:
    """Compute expected_from_scores and measured blocks for selected customers."""
    n_selected = len(selected_df)
    total_spend = n_selected * cost_per_customer_bdt
    budget_respected = total_spend <= budget_bdt

    selected_indices = selected_df.index.tolist()
    customer_ids = (
        selected_df["customer_id"].tolist()
        if has_customer_id and "customer_id" in selected_df.columns
        else selected_indices
    )

    # -------------------------------------------------------------------------
    # Block 1: Expected From Scores
    # -------------------------------------------------------------------------
    if n_selected > 0:
        mean_p_treat = (
            float(np.mean(selected_df["p_treat"]))
            if "p_treat" in selected_df.columns
            else None
        )
        uplift_series = (
            selected_df["uplift"]
            if "uplift" in selected_df.columns
            else None
        )
        if uplift_series is not None:
            mean_uplift = float(np.mean(uplift_series))
            expected_incremental_txns = float(np.sum(uplift_series))
            neg_share = float(np.mean(uplift_series < 0.0))
        else:
            mean_uplift = None
            expected_incremental_txns = None
            neg_share = None

        if expected_incremental_txns is not None and expected_incremental_txns > 0:
            exp_cost_per_inc = round(total_spend / expected_incremental_txns, 2)
        else:
            exp_cost_per_inc = None
    else:
        mean_p_treat = None
        mean_uplift = None
        expected_incremental_txns = 0.0
        neg_share = 0.0
        exp_cost_per_inc = None

    expected_block = {
        "mean_predicted_response": round(mean_p_treat, 5) if mean_p_treat is not None else None,
        "mean_predicted_uplift": round(mean_uplift, 5) if mean_uplift is not None else None,
        "expected_incremental_transactions": round(expected_incremental_txns, 4) if expected_incremental_txns is not None else None,
        "negative_uplift_share": round(neg_share, 4) if neg_share is not None else None,
        "expected_cost_per_incremental_txn_bdt": exp_cost_per_inc,
    }

    # -------------------------------------------------------------------------
    # Block 2: Measured (Factual outcomes only)
    # -------------------------------------------------------------------------
    if n_selected > 0 and TARGET_COLUMN in selected_df.columns and TREATMENT_COLUMN in selected_df.columns:
        y = selected_df[TARGET_COLUMN].values
        t = selected_df[TREATMENT_COLUMN].values

        n_t = int(np.sum(t == 1))
        n_c = int(np.sum(t == 0))
        has_both_arms = n_t > 0 and n_c > 0

        # Support check using the 30/30 rule
        inc_support = compute_incremental_response(y, t, min_support=30)
        treatment_rate = compute_treatment_rate(t)

        treated_resp = int(np.sum(y[t == 1])) if n_t > 0 else 0
        control_resp = int(np.sum(y[t == 0])) if n_c > 0 else 0

        factual_treated_rate = float(treated_resp / n_t) if n_t > 0 else None
        factual_control_rate = float(control_resp / n_c) if n_c > 0 else None

        if has_both_arms and factual_treated_rate is not None and factual_control_rate is not None:
            measured_diff = factual_treated_rate - factual_control_rate
            measured_inc_txns = n_selected * measured_diff
            if measured_inc_txns > 0:
                cost_ratio = round(total_spend / measured_inc_txns, 2)
                cost_ratio_note = None
            else:
                cost_ratio = None
                cost_ratio_note = "undefined (incremental transactions <= 0)"
        else:
            measured_diff = None
            measured_inc_txns = None
            cost_ratio = None
            cost_ratio_note = "undefined (missing arm in selected cohort)"

        measured_block = {
            "n_selected": n_selected,
            "n_treated": n_t,
            "n_control": n_c,
            "treatment_rate": round(treatment_rate, 4),
            "treated_responders": treated_resp,
            "control_responders": control_resp,
            "factual_treated_rate": round(factual_treated_rate, 5) if factual_treated_rate is not None else None,
            "factual_control_rate": round(factual_control_rate, 5) if factual_control_rate is not None else None,
            "measured_incremental_rate": round(measured_diff, 5) if measured_diff is not None else None,
            "measured_incremental_transactions": round(measured_inc_txns, 4) if measured_inc_txns is not None else None,
            "measured_cost_per_incremental_txn_bdt": cost_ratio,
            "measured_cost_ratio_note": cost_ratio_note,
            "has_both_arms": has_both_arms,
            "has_sufficient_support": inc_support.has_sufficient_support,
            "support_status": inc_support.status,
        }
    else:
        measured_block = {
            "n_selected": n_selected,
            "status": "factual_data_not_available",
        }

    return StrategyEvaluation(
        strategy_name=strategy_name,
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
        total_spend_bdt=total_spend,
        budget_respected=budget_respected,
        selected_count=n_selected,
        selected_indices=selected_indices,
        selected_customer_ids=customer_ids,
        expected_from_scores=expected_block,
        measured=measured_block,
    )


def compare_strategies(
    eval_df: pd.DataFrame,
    budget_bdt: float = DEFAULT_BUDGET_BDT,
    cost_per_customer_bdt: float = DEFAULT_COST_PER_CUSTOMER_BDT,
    random_seed: int = DEFAULT_RANDOM_SEED,
    exclude_negative_uplift: bool = True,
    campaign_id: Optional[str] = None,
) -> StrategyComparisonResult:
    """Compare Random, Response, and Uplift targeting policies on a scored cohort.

    Args:
        eval_df: Scored DataFrame containing 'p_treat' and 'uplift', and optionally
                 factual columns 'y_transacted' and 'treatment'.
        budget_bdt: Maximum spend limit (must be > 0).
        cost_per_customer_bdt: Uniform cost to contact one customer (must be > 0).
        random_seed: Seed for random selection reproducibility.
        exclude_negative_uplift: If True, uplift strategy ignores customers with uplift < 0.
        campaign_id: Optional campaign identifier (used to salt random seed).

    Returns:
        StrategyComparisonResult with complete expected and measured blocks.
    """
    if budget_bdt <= 0:
        raise ValueError(f"budget_bdt must be positive, got {budget_bdt}")
    if cost_per_customer_bdt <= 0:
        raise ValueError(f"cost_per_customer_bdt must be positive, got {cost_per_customer_bdt}")
    if len(eval_df) == 0:
        raise ValueError("eval_df cannot be empty")

    n_available = len(eval_df)
    max_selectable = int(budget_bdt // cost_per_customer_bdt)
    target_count = min(n_available, max_selectable)

    # -------------------------------------------------------------------------
    # 1. Strategy: Random
    # -------------------------------------------------------------------------
    seed_offset = hash(campaign_id) % 10000 if campaign_id else 0
    rng = np.random.RandomState((random_seed + seed_offset) & 0x7FFFFFFF)
    random_perm = rng.permutation(n_available)
    random_selected_idx = eval_df.index[random_perm[:target_count]]
    random_selected_df = eval_df.loc[random_selected_idx]

    res_random = _evaluate_selected_cohort(
        selected_df=random_selected_df,
        strategy_name="random",
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
    )

    # -------------------------------------------------------------------------
    # 2. Strategy: Response (p_treat descending)
    # -------------------------------------------------------------------------
    if "p_treat" not in eval_df.columns:
        raise ValueError("eval_df missing required column 'p_treat' for response strategy")

    # Sort descending by p_treat
    response_sorted = eval_df.sort_values(by="p_treat", ascending=False, kind="mergesort")
    response_selected_df = response_sorted.iloc[:target_count]

    res_response = _evaluate_selected_cohort(
        selected_df=response_selected_df,
        strategy_name="response",
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
    )

    # -------------------------------------------------------------------------
    # 3. Strategy: Uplift (predicted uplift descending)
    # -------------------------------------------------------------------------
    if "uplift" not in eval_df.columns:
        raise ValueError("eval_df missing required column 'uplift' for uplift strategy")

    uplift_candidates = eval_df.copy()
    if exclude_negative_uplift:
        uplift_candidates = uplift_candidates[uplift_candidates["uplift"] >= 0.0]

    uplift_sorted = uplift_candidates.sort_values(by="uplift", ascending=False, kind="mergesort")
    uplift_selected_df = uplift_sorted.iloc[:target_count]

    res_uplift = _evaluate_selected_cohort(
        selected_df=uplift_selected_df,
        strategy_name="uplift",
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
    )

    # -------------------------------------------------------------------------
    # Check identity of selections between Response and Uplift
    # -------------------------------------------------------------------------
    response_set = set(res_response.selected_indices)
    uplift_set = set(res_uplift.selected_indices)
    selections_identical = (response_set == uplift_set)

    if selections_identical:
        if target_count >= n_available:
            identical_reason = "Budget accommodates the entire audience; all available customers selected."
        elif np.allclose(eval_df["p_treat"], eval_df["uplift"]):
            identical_reason = "Response and uplift scores are numerically identical."
        else:
            identical_reason = "Both rankings selected the identical customer subset under this budget."
    else:
        identical_reason = None

    return StrategyComparisonResult(
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
        total_available_customers=n_available,
        max_selectable_customers=max_selectable,
        random=res_random,
        response=res_response,
        uplift=res_uplift,
        selections_identical=selections_identical,
        identical_reason=identical_reason,
    )


def run_smoke_strategy_comparison(
    dataset_dir: Union[str, Path] = "data/fixtures/fixture_v1",
    budget_bdt: float = 100.0,
    cost_per_customer_bdt: float = 10.0,
) -> Dict[str, Any]:
    """Execute smoke run comparing strategies on the validation split of a dataset."""
    from .uplift import train_logistic_t_learner

    train_df, val_df = load_train_val(dataset_dir)
    learner = train_logistic_t_learner(train_df)
    preds = learner.predict_uplift(val_df)

    scored_val = val_df.copy()
    scored_val["p_treat"] = preds.p_treat
    scored_val["p_control"] = preds.p_control
    scored_val["uplift"] = preds.uplift

    comp_result = compare_strategies(
        eval_df=scored_val,
        budget_bdt=budget_bdt,
        cost_per_customer_bdt=cost_per_customer_bdt,
    )

    return comp_result.to_dict()


if __name__ == "__main__":
    result = run_smoke_strategy_comparison()
    print("Strategy Comparison Smoke Results:")
    print(json.dumps(result, indent=2))
