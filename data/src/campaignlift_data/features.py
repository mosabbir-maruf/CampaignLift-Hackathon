"""Feature table builder for CampaignLift synthetic causal world.

Constructs one feature row per eligible exposed customer strictly using pre-assignment
history (< assigned_at), static customer attributes, campaign parameters, randomized
treatment assignment, and observed factual conversion labels.

Enforces zero leakage of forbidden training columns (latent attributes, potential outcomes, true uplift).
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .campaigns import DEFAULT_CAMPAIGN_START_DATE, get_current_campaign
from .config import load_world_config
from .exposures import compute_observed_fatigue_features

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


def compute_transaction_aggregates(
    customer_txns: List[Dict[str, Any]],
    assigned_dt: datetime,
) -> Dict[str, Union[int, float]]:
    """Compute pre-assignment transaction aggregates for a single customer.

    Events occurring at or after assigned_dt are strictly excluded.
    """
    d90_cutoff = assigned_dt - timedelta(days=90)
    d30_cutoff = assigned_dt - timedelta(days=30)

    # Strictly prior to assigned_dt (event_dt < assigned_dt)
    valid_txns: List[Tuple[datetime, Dict[str, Any]]] = []
    for t in customer_txns:
        event_dt = datetime.fromisoformat(t["event_time"].replace("Z", "+00:00"))
        if event_dt < assigned_dt and event_dt >= d90_cutoff:
            valid_txns.append((event_dt, t))

    txn_count_90d = len(valid_txns)
    txn_amount_90d_bdt = round(sum(t["amount_bdt"] for _, t in valid_txns), 2)

    # 30-day window metrics
    txns_30d = [t for dt, t in valid_txns if dt >= d30_cutoff]
    txn_count_30d = len(txns_30d)
    txn_amount_30d_bdt = round(sum(t["amount_bdt"] for t in txns_30d), 2)

    # Shares over 90-day window
    if txn_count_90d > 0:
        qr_count = sum(1 for _, t in valid_txns if t.get("txn_type") == "qr_pay")
        cashout_count = sum(1 for _, t in valid_txns if t.get("txn_type") == "cash_out")
        merchant_count = sum(1 for _, t in valid_txns if t.get("txn_type") == "merchant_pay")
        app_count = sum(1 for _, t in valid_txns if t.get("channel") == "app")

        qr_txn_share_90d = round(qr_count / txn_count_90d, 4)
        cashout_share_90d = round(cashout_count / txn_count_90d, 4)
        merchant_pay_share_90d = round(merchant_count / txn_count_90d, 4)
        app_channel_share_90d = round(app_count / txn_count_90d, 4)
        avg_ticket_90d_bdt = round(txn_amount_90d_bdt / txn_count_90d, 2)

        latest_dt = max(dt for dt, _ in valid_txns)
        days_since_last_txn = max(0, (assigned_dt.date() - latest_dt.date()).days)
    else:
        qr_txn_share_90d = 0.0
        cashout_share_90d = 0.0
        merchant_pay_share_90d = 0.0
        app_channel_share_90d = 0.0
        avg_ticket_90d_bdt = 0.0
        days_since_last_txn = 999

    return {
        "txn_count_30d": txn_count_30d,
        "txn_count_90d": txn_count_90d,
        "txn_amount_30d_bdt": txn_amount_30d_bdt,
        "txn_amount_90d_bdt": txn_amount_90d_bdt,
        "qr_txn_share_90d": qr_txn_share_90d,
        "cashout_share_90d": cashout_share_90d,
        "merchant_pay_share_90d": merchant_pay_share_90d,
        "days_since_last_txn": days_since_last_txn,
        "avg_ticket_90d_bdt": avg_ticket_90d_bdt,
        "app_channel_share_90d": app_channel_share_90d,
    }


def build_feature_table(
    customers: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    prior_exposures: List[Dict[str, Any]],
    exposures: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
    campaign: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    assigned_at: Optional[Union[date, datetime, str]] = None,
) -> List[Dict[str, Any]]:
    """Build a modeling feature table containing one row per eligible customer.

    Args:
        customers: List of customer static records.
        transactions: List of historical transaction records.
        prior_exposures: List of prior historical campaign exposures.
        exposures: List of randomized exposure records (eligible customers only).
        outcomes: List of factual outcome records (with y_transacted).
        campaign: Modeled campaign dict (defaults to get_current_campaign()).
        config: Optional loaded world.yaml configuration.
        assigned_at: Campaign assignment timestamp.

    Returns:
        List of dicts strictly conforming to feature_table.schema.json.
    """
    if config is None:
        config = load_world_config()

    if campaign is None:
        campaign = get_current_campaign(config=config)

    campaign_id = campaign["campaign_id"]
    objective = campaign["objective"]
    offer_type = campaign["offer_type"]
    incentive_value = float(campaign["incentive_value"])
    incentive_cost_bdt = float(campaign["incentive_cost_bdt"])

    # Resolve assignment datetime in UTC
    if assigned_at is None:
        start_d = date.fromisoformat(campaign["start_date"])
        assigned_dt = datetime.combine(start_d, datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(assigned_at, str):
        if "T" in assigned_at:
            assigned_dt = datetime.fromisoformat(assigned_at.replace("Z", "+00:00"))
        else:
            assigned_dt = datetime.combine(date.fromisoformat(assigned_at), datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(assigned_at, date) and not isinstance(assigned_at, datetime):
        assigned_dt = datetime.combine(assigned_at, datetime.min.time(), tzinfo=timezone.utc)
    else:
        assigned_dt = assigned_at.astimezone(timezone.utc) if assigned_at.tzinfo else assigned_at.replace(tzinfo=timezone.utc)

    # Index lookups
    customers_by_id = {c["customer_id"]: c for c in customers}
    outcomes_by_id = {o["customer_id"]: o for o in outcomes}

    txns_by_id: Dict[str, List[Dict[str, Any]]] = {}
    for t in transactions:
        txns_by_id.setdefault(t["customer_id"], []).append(t)

    prior_exps_by_id: Dict[str, List[Dict[str, Any]]] = {}
    for pe in prior_exposures:
        prior_exps_by_id.setdefault(pe["customer_id"], []).append(pe)

    feature_rows: List[Dict[str, Any]] = []

    # One row per exposure in the randomized experiment
    for exp in exposures:
        cid = exp["customer_id"]
        cust = customers_by_id.get(cid)
        outcome = outcomes_by_id.get(cid)

        if not cust or not outcome:
            continue

        # 1. Static customer features
        signup_d = date.fromisoformat(cust["signup_date"])
        tenure_days = max(0, (assigned_dt.date() - signup_d).days)

        # 2. Pre-assignment transaction aggregates
        cust_txns = txns_by_id.get(cid, [])
        txn_aggs = compute_transaction_aggregates(cust_txns, assigned_dt=assigned_dt)

        # 3. Observed fatigue features from prior exposures
        cust_priors = prior_exps_by_id.get(cid, [])
        fatigue_feats = compute_observed_fatigue_features(
            customer_id=cid,
            exposures=cust_priors,
            assigned_date=assigned_dt.date(),
        )

        row = {
            "customer_id": cid,
            "campaign_id": campaign_id,
            "tenure_days": tenure_days,
            "age_band": cust["age_band"],
            "region_code": cust["region_code"],
            "kyc_level": cust["kyc_level"],
            "acquisition_channel": cust["acquisition_channel"],
            "txn_count_30d": txn_aggs["txn_count_30d"],
            "txn_count_90d": txn_aggs["txn_count_90d"],
            "txn_amount_30d_bdt": txn_aggs["txn_amount_30d_bdt"],
            "txn_amount_90d_bdt": txn_aggs["txn_amount_90d_bdt"],
            "qr_txn_share_90d": txn_aggs["qr_txn_share_90d"],
            "cashout_share_90d": txn_aggs["cashout_share_90d"],
            "merchant_pay_share_90d": txn_aggs["merchant_pay_share_90d"],
            "days_since_last_txn": txn_aggs["days_since_last_txn"],
            "avg_ticket_90d_bdt": txn_aggs["avg_ticket_90d_bdt"],
            "app_channel_share_90d": txn_aggs["app_channel_share_90d"],
            "campaign_exposures_prior_30d": fatigue_feats["campaign_exposures_prior_30d"],
            "campaign_exposures_prior_90d": fatigue_feats["campaign_exposures_prior_90d"],
            "days_since_last_campaign": fatigue_feats["days_since_last_campaign"],
            "objective": objective,
            "offer_type": offer_type,
            "incentive_value": incentive_value,
            "incentive_cost_bdt": incentive_cost_bdt,
            "treatment": exp["treatment"],
            "y_transacted": outcome["y_transacted"],
        }

        # Assert no forbidden column in output row
        forbidden_intersect = set(row.keys()) & FORBIDDEN_COLUMNS
        if forbidden_intersect:
            raise ValueError(f"Forbidden columns detected in feature row: {forbidden_intersect}")

        feature_rows.append(row)

    return feature_rows
