"""Outcome simulator and potential outcomes (true uplift) generator for CampaignLift causal world.

Computes potential outcome probabilities (p_y_control, p_y_treat) and true uplift (tau = p_treat - p_control).
Simulates factual conversion outcomes (y_transacted, txn_count_window, txn_amount_window_bdt)
under the observed treatment arm.

Strictly preserves separation:
- Factual outcomes are written to the public outcome frame.
- True uplift and potential probabilities are stored exclusively in the hidden oracle evaluation frame.
"""

from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from .campaigns import DEFAULT_CAMPAIGN_START_DATE, get_current_campaign
from .config import load_world_config
from .seeds import get_stage_seed


def sigmoid(z: float) -> float:
    """Compute standard sigmoid function with numerical overflow protection."""
    if z >= 35.0:
        return 1.0
    if z <= -35.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def compute_potential_outcomes(
    customers: List[Dict[str, Any]],
    customer_latents: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    campaign: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Compute potential outcome probabilities and true uplift for eligible customers.

    Args:
        customers: List of customer dicts.
        customer_latents: List of corresponding customer latent dicts.
        transactions: Pre-assignment transactions list.
        campaign: Modeled campaign dictionary.
        config: Optional loaded world.yaml configuration.
        seed: Random seed for idiosyncratic logit shock. Defaults to stage seed.

    Returns:
        List of dicts conforming strictly to hidden_uplift.schema.json.
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("outcome_noise_and_bernoulli", config=config)

    rng_noise = random.Random(seed)

    scoring_cfg = config.get("causal_scoring", {})
    ctrl_cfg = scoring_cfg.get("control_score", {})
    treat_cfg = scoring_cfg.get("treated_score", {})
    annoy_cfg = treat_cfg.get("negative_uplift_annoyance", {})
    clip_min = scoring_cfg.get("probability_clip", {}).get("min", 0.01)
    clip_max = scoring_cfg.get("probability_clip", {}).get("max", 0.99)
    noise_sd = scoring_cfg.get("noise", {}).get("standard_deviation", 0.20)

    # Campaign properties
    campaign_id = campaign["campaign_id"]
    objective = campaign.get("objective", "qr_adoption")
    incentive_val = float(campaign.get("incentive_value", 20.0))
    incentive_strength = min(1.0, max(0.0, incentive_val / 50.0))

    # Pre-index latents and 30d activity
    latents_by_id = {lat["customer_id"]: lat for lat in customer_latents}

    # Determine 30-day cutoff for recent activity
    start_d = date.fromisoformat(campaign["start_date"])
    assigned_dt = datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc)
    d30_cutoff = assigned_dt - timedelta(days=30)

    cust_has_recent_30d: Dict[str, float] = {}
    for t in transactions:
        cid = t["customer_id"]
        event_dt = datetime.fromisoformat(t["event_time"].replace("Z", "+00:00"))
        if event_dt >= d30_cutoff:
            cust_has_recent_30d[cid] = 1.0

    hidden_uplifts: List[Dict[str, Any]] = []

    for cust in customers:
        cid = cust["customer_id"]
        lat = latents_by_id.get(cid)
        if not lat:
            continue

        nat_prop = float(lat["natural_transaction_propensity"])
        dig_mat = float(lat["digital_maturity"])
        camp_sens = float(lat["campaign_sensitivity"])
        price_sens = float(lat["price_sensitivity"])
        qr_aff = float(lat["qr_affinity"])
        fatigue = float(lat["offer_fatigue"])
        profile = lat.get("profile", "")

        recent_act = cust_has_recent_30d.get(cid, 0.0)

        # 1. Control logit score
        logit_control = (
            ctrl_cfg.get("intercept", -1.5)
            + ctrl_cfg.get("weights", {}).get("natural_transaction_propensity", 2.2) * nat_prop
            + ctrl_cfg.get("weights", {}).get("digital_maturity", 0.8) * dig_mat
            + ctrl_cfg.get("weights", {}).get("recent_activity_term", 0.5) * recent_act
        )

        # 2. Treated logit score
        t_weights = treat_cfg.get("weights", {})
        logit_treated = (
            treat_cfg.get("intercept", -1.5)
            + t_weights.get("natural_transaction_propensity", 2.2) * nat_prop
            + t_weights.get("digital_maturity", 0.8) * dig_mat
            + t_weights.get("recent_activity_term", 0.5) * recent_act
            + t_weights.get("campaign_sensitivity", 1.8) * camp_sens
            + t_weights.get("price_sensitivity_x_incentive", 1.5) * (price_sens * incentive_strength)
        )

        # Offer match term
        if objective == "qr_adoption":
            logit_treated += t_weights.get("offer_match_qr", 1.2) * qr_aff
        elif objective == "reactivation":
            logit_treated += t_weights.get("offer_match_reactivation", 1.0) * (1.0 - recent_act)
        elif objective == "retention":
            logit_treated += t_weights.get("offer_match_retention", -0.4) * 1.0
        else:
            logit_treated += 0.5

        # Offer fatigue penalty (negative weight)
        fatigue_penalty_weight = t_weights.get("offer_fatigue_penalty", -1.6)
        logit_treated += fatigue_penalty_weight * fatigue

        # Negative uplift annoyance mechanism
        if annoy_cfg.get("enabled", True):
            fatigue_thresh = annoy_cfg.get("fatigue_threshold", 0.60)
            sens_thresh = annoy_cfg.get("campaign_sensitivity_threshold", 0.25)
            base_annoyance = annoy_cfg.get("annoyance_penalty", -2.0)
            prof_mult = annoy_cfg.get("profile_multiplier", 1.5)

            if fatigue >= fatigue_thresh and camp_sens <= sens_thresh:
                mult = prof_mult if profile == "negative_uplift" else 1.0
                logit_treated += base_annoyance * mult
            elif profile == "negative_uplift":
                logit_treated += base_annoyance * 1.0

        # Idiosyncratic logit shock
        noise = rng_noise.gauss(0.0, noise_sd)

        # Potential probabilities clipped strictly to [clip_min, clip_max]
        p_control = round(min(clip_max, max(clip_min, sigmoid(logit_control + noise))), 6)
        p_treat = round(min(clip_max, max(clip_min, sigmoid(logit_treated + noise))), 6)
        true_uplift = round(p_treat - p_control, 6)

        hidden_record = {
            "customer_id": cid,
            "campaign_id": campaign_id,
            "natural_transaction_propensity": nat_prop,
            "qr_affinity": qr_aff,
            "price_sensitivity": price_sens,
            "campaign_sensitivity": camp_sens,
            "digital_maturity": dig_mat,
            "offer_fatigue": fatigue,
            "p_y_control": p_control,
            "p_y_treat": p_treat,
            "true_uplift": true_uplift,
        }
        hidden_uplifts.append(hidden_record)

    return hidden_uplifts


def simulate_factual_outcomes(
    exposures: List[Dict[str, Any]],
    hidden_uplifts: List[Dict[str, Any]],
    campaign: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Simulate factual conversion outcomes under the realized treatment condition.

    Args:
        exposures: List of exposure dicts with randomized treatment flags (T in {0, 1}).
        hidden_uplifts: Potential outcomes dicts containing p_y_control and p_y_treat.
        campaign: Modeled campaign dictionary.
        config: Optional loaded world.yaml configuration.
        seed: Random seed for Bernoulli draws and outcome transaction values.

    Returns:
        List of dicts conforming strictly to outcome.schema.json (factual only).
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("outcome_noise_and_bernoulli", config=config)

    # Offset seed slightly for independent factual draw sequence
    rng_draw = random.Random(seed + 100)

    campaign_id = campaign["campaign_id"]
    start_d = date.fromisoformat(campaign["start_date"])
    outcome_window_days = int(campaign.get("outcome_window_days", 14))

    window_start_dt = datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc)
    window_end_dt = window_start_dt + timedelta(days=outcome_window_days)

    window_start_str = window_start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    window_end_str = window_end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Index potential outcomes by customer_id
    hidden_by_id = {h["customer_id"]: h for h in hidden_uplifts}

    outcomes: List[Dict[str, Any]] = []

    for exp in exposures:
        cid = exp["customer_id"]
        hidden = hidden_by_id.get(cid)
        if not hidden:
            continue

        treatment = exp["treatment"]
        p_factual = hidden["p_y_treat"] if treatment == 1 else hidden["p_y_control"]

        # Bernoulli draw for binary transaction outcome Y
        y_transacted = 1 if rng_draw.random() < p_factual else 0

        # Maintain strict consistency with y_transacted:
        # If y_transacted == 0: txn_count_window == 0, txn_amount_window_bdt == 0.0
        # If y_transacted == 1: txn_count_window >= 1, txn_amount_window_bdt > 0.0
        if y_transacted == 1:
            # Active transactor in window: 1 to 4 transactions typical
            txn_count_window = rng_draw.randint(1, 4)
            unit_amounts = [
                rng_draw.expovariate(1 / 400.0) + 50.0 for _ in range(txn_count_window)
            ]
            txn_amount_window_bdt = round(min(50000.0, max(20.0, sum(unit_amounts))), 2)
        else:
            txn_count_window = 0
            txn_amount_window_bdt = 0.0

        outcome_record = {
            "customer_id": cid,
            "campaign_id": campaign_id,
            "y_transacted": y_transacted,
            "txn_count_window": txn_count_window,
            "txn_amount_window_bdt": txn_amount_window_bdt,
            "window_start": window_start_str,
            "window_end": window_end_str,
        }
        outcomes.append(outcome_record)

    return outcomes


def generate_outcomes_and_hidden_uplift(
    customers: List[Dict[str, Any]],
    customer_latents: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    exposures: List[Dict[str, Any]],
    campaign: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simulate both potential outcomes (hidden oracle) and factual observed outcomes.

    Returns:
        (outcomes, hidden_uplifts):
            outcomes: Factual outcomes conforming to outcome.schema.json.
            hidden_uplifts: Oracle potential outcomes conforming to hidden_uplift.schema.json.
    """
    if config is None:
        config = load_world_config()

    if campaign is None:
        campaign = get_current_campaign(config=config)

    hidden_uplifts = compute_potential_outcomes(
        customers=customers,
        customer_latents=customer_latents,
        transactions=transactions,
        campaign=campaign,
        config=config,
        seed=seed,
    )

    outcomes = simulate_factual_outcomes(
        exposures=exposures,
        hidden_uplifts=hidden_uplifts,
        campaign=campaign,
        config=config,
        seed=seed,
    )

    return outcomes, hidden_uplifts
