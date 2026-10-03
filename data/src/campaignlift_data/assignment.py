"""Treatment assignment and eligibility module for CampaignLift causal world.

Evaluates customer eligibility strictly using pre-assignment history and tenure.
Assigns randomized treatment (T in {0, 1}) with probability 0.5 to eligible customers.
Ineligible customers are logged to an audit trail and excluded from the exposure file.
"""

from datetime import date, datetime, timedelta, timezone
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from .campaigns import DEFAULT_CAMPAIGN_START_DATE, get_current_campaign
from .config import load_world_config
from .seeds import get_stage_seed


def evaluate_customer_eligibility(
    customer: Dict[str, Any],
    customer_txns: List[Dict[str, Any]],
    objective: str,
    config: Optional[Dict[str, Any]] = None,
    assigned_dt: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Evaluate whether a customer is eligible for a marketing campaign.

    Eligibility is determined strictly from static profile attributes (tenure)
    and pre-assignment transaction history. Never reads future outcomes.

    Args:
        customer: Customer record dict.
        customer_txns: List of pre-assignment transactions for this customer.
        objective: Marketing objective ('activation', 'reactivation', 'qr_adoption', 'retention').
        config: Optional loaded world.yaml configuration.
        assigned_dt: Campaign assignment datetime in UTC.

    Returns:
        (is_eligible, audit_reason)
    """
    if config is None:
        config = load_world_config()

    if assigned_dt is None:
        assigned_dt = datetime.combine(
            DEFAULT_CAMPAIGN_START_DATE, datetime.min.time(), tzinfo=timezone.utc
        )

    assigned_d = assigned_dt.date()
    signup_d = date.fromisoformat(customer["signup_date"])
    tenure_days = (assigned_d - signup_d).days

    rules_config = config.get("eligibility", {}).get("rules", {})
    d30_cutoff = assigned_dt - timedelta(days=30)

    # Compute historical summary metrics from pre-assignment transactions
    txn_count_90d = len(customer_txns)
    txn_count_30d = 0
    qr_txn_count_90d = 0

    for t in customer_txns:
        event_dt = datetime.fromisoformat(t["event_time"].replace("Z", "+00:00"))
        if event_dt >= d30_cutoff:
            txn_count_30d += 1
        if t["txn_type"] == "qr_pay":
            qr_txn_count_90d += 1

    qr_share_90d = (qr_txn_count_90d / txn_count_90d) if txn_count_90d > 0 else 0.0

    if objective == "activation":
        max_tenure = rules_config.get("activation", {}).get("criteria", {}).get("max_tenure_days", 30)
        if tenure_days <= max_tenure:
            return True, "Eligible for activation (tenure <= 30d)"
        return False, f"Ineligible: tenure {tenure_days}d > max {max_tenure}d"

    elif objective == "reactivation":
        min_tenure = rules_config.get("reactivation", {}).get("criteria", {}).get("min_tenure_days", 31)
        max_30d = rules_config.get("reactivation", {}).get("criteria", {}).get("max_txn_count_30d", 0)
        if tenure_days >= min_tenure and txn_count_30d <= max_30d:
            return True, "Eligible for reactivation (tenure > 30d and 0 txns in last 30d)"
        if tenure_days < min_tenure:
            return False, f"Ineligible: tenure {tenure_days}d < min {min_tenure}d"
        return False, f"Ineligible: active in last 30d ({txn_count_30d} txns > {max_30d})"

    elif objective == "qr_adoption":
        min_txns = rules_config.get("qr_adoption", {}).get("criteria", {}).get("min_historical_txns_90d", 1)
        max_qr_share = rules_config.get("qr_adoption", {}).get("criteria", {}).get("max_qr_txn_share_90d", 0.20)
        if txn_count_90d >= min_txns and qr_share_90d <= max_qr_share:
            return True, f"Eligible for qr_adoption (txns={txn_count_90d}, qr_share={qr_share_90d:.2f} <= {max_qr_share})"
        if txn_count_90d < min_txns:
            return False, f"Ineligible: no historical transactions ({txn_count_90d} < {min_txns})"
        return False, f"Ineligible: QR share {qr_share_90d:.2f} exceeds cap {max_qr_share}"

    elif objective == "retention":
        min_30d = rules_config.get("retention", {}).get("criteria", {}).get("min_txn_count_30d", 1)
        if txn_count_30d >= min_30d:
            return True, f"Eligible for retention ({txn_count_30d} txns in 30d >= {min_30d})"
        return False, f"Ineligible: no transactions in last 30d ({txn_count_30d} < {min_30d})"

    else:
        # Default fallback: eligible if any transaction
        return True, "Eligible by default"


def assign_treatment(
    customers: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    campaign: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
    assigned_at: Optional[Union[date, datetime, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Assign randomized treatment to eligible customers for the modeled campaign.

    Eligibility is evaluated per customer using pre-assignment history.
    Ineligible customers are output into an audit list.
    Eligible customers receive randomized treatment (1) or control (0) with p=0.5.

    Args:
        customers: List of customer dicts.
        transactions: List of pre-assignment transaction dicts.
        campaign: Modeled campaign dict (defaults to get_current_campaign()).
        config: Optional loaded world.yaml configuration.
        seed: Optional integer seed (defaults to stage seed 'treatment_assignment').
        assigned_at: Assignment timestamp (defaults to campaign start_date at 00:00:00Z).

    Returns:
        (exposures, ineligible_audit):
            exposures: List of dicts conforming to exposure.schema.json (eligible customers only).
            ineligible_audit: List of audit records for ineligible customers.
    """
    if config is None:
        config = load_world_config()

    if campaign is None:
        campaign = get_current_campaign(config=config)

    campaign_id = campaign["campaign_id"]
    objective = campaign["objective"]

    if seed is None:
        seed = get_stage_seed("treatment_assignment", config=config)

    rng = random.Random(seed)

    # Resolve assignment datetime
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

    assigned_at_str = assigned_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Index transactions by customer_id for fast lookup
    txns_by_cust: Dict[str, List[Dict[str, Any]]] = {}
    for t in transactions:
        txns_by_cust.setdefault(t["customer_id"], []).append(t)

    exposures: List[Dict[str, Any]] = []
    ineligible_audit: List[Dict[str, Any]] = []
    exp_counter = 1

    for cust in customers:
        cid = cust["customer_id"]
        cust_txns = txns_by_cust.get(cid, [])

        is_eligible, reason = evaluate_customer_eligibility(
            customer=cust,
            customer_txns=cust_txns,
            objective=objective,
            config=config,
            assigned_dt=assigned_dt,
        )

        if not is_eligible:
            ineligible_audit.append({
                "customer_id": cid,
                "campaign_id": campaign_id,
                "eligible": False,
                "reason": reason,
                "assigned_at": assigned_at_str,
            })
            continue

        # Customer is eligible: assign treatment with randomized probability 0.5
        treatment = 1 if rng.random() < 0.5 else 0

        exp_record = {
            "exposure_id": f"EXP{exp_counter:08d}",
            "customer_id": cid,
            "campaign_id": campaign_id,
            "eligible": True,
            "treatment": treatment,
            "assignment_probability": 0.5,
            "assigned_at": assigned_at_str,
        }
        exposures.append(exp_record)
        exp_counter += 1

    return exposures, ineligible_audit
