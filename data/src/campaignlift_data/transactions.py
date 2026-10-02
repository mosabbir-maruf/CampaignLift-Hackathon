"""Transaction history generator for CampaignLift synthetic causal world.

Generates 90-day pre-assignment transaction logs. Transaction volume is driven
by natural propensity and digital maturity, QR share rises with qr_affinity,
and app channel share rises with digital maturity. All events occur strictly before
campaign assignment.
"""

from datetime import date, datetime, timedelta, timezone
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from .config import load_world_config
from .customers import DEFAULT_CAMPAIGN_START_DATE
from .seeds import get_stage_seed

# Transaction types and directions
TXN_TYPES_INFLOW = ["cash_in", "p2p_receive"]
TXN_TYPES_OUTFLOW_GENERAL = ["cash_out", "p2p_send", "recharge", "bill_pay"]
TXN_TYPES_MERCHANT = ["merchant_pay", "qr_pay"]
MERCHANT_CATEGORIES = ["grocery", "transport", "food", "telecom", "other"]


def _poisson_draw(rng: random.Random, lam: float) -> int:
    """Draw a Poisson-distributed integer using Knuth's algorithm."""
    if lam <= 0:
        return 0
    if lam > 50:
        # Gaussian approximation for large lambda
        val = rng.gauss(lam, math.sqrt(lam))
        return max(0, int(round(val)))
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def generate_transactions(
    customers: List[Dict[str, Any]],
    customer_latents: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
    campaign_start: Optional[Union[date, datetime]] = None,
) -> List[Dict[str, Any]]:
    """Generate 90-day pre-assignment transaction records for a cohort of customers.

    Args:
        customers: List of customer dictionaries (from generate_customers).
        customer_latents: List of corresponding latent dictionaries (from generate_customers).
        config: Optional loaded world.yaml configuration dictionary.
        seed: Optional integer seed for transaction generation. Defaults to stage seed.
        campaign_start: Campaign assignment timestamp or date. Transactions occur strictly before this.

    Returns:
        List of transaction records conforming to transaction.schema.json,
        ordered chronologically by event_time.
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("transactions", config=config)

    rng = random.Random(seed)

    # Resolve assignment datetime (UTC)
    if campaign_start is None:
        assigned_dt = datetime.combine(DEFAULT_CAMPAIGN_START_DATE, datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(campaign_start, date) and not isinstance(campaign_start, datetime):
        assigned_dt = datetime.combine(campaign_start, datetime.min.time(), tzinfo=timezone.utc)
    else:
        assigned_dt = campaign_start.astimezone(timezone.utc) if campaign_start.tzinfo else campaign_start.replace(tzinfo=timezone.utc)

    history_days = config.get("timeline", {}).get("history_days", 90)
    history_start_dt = assigned_dt - timedelta(days=history_days)

    # Base active customer transaction volume target (near 25 txns/90d as per data plan)
    base_volume = 24.0

    # Index latents by customer_id for fast lookup
    latents_by_id = {lat["customer_id"]: lat for lat in customer_latents}

    all_transactions: List[Dict[str, Any]] = []
    global_txn_counter = 1

    for cust in customers:
        cust_id = cust["customer_id"]
        lat = latents_by_id.get(cust_id)
        if not lat:
            continue

        nat_propensity = lat["natural_transaction_propensity"]
        dig_maturity = lat["digital_maturity"]
        qr_affinity = lat["qr_affinity"]

        # Parse customer signup date
        signup_dt = datetime.combine(
            date.fromisoformat(cust["signup_date"]),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        # Active observation window for this customer: max(signup_date, history_start_dt) to assigned_dt - 1 sec
        window_start = max(signup_dt, history_start_dt)
        window_seconds = int((assigned_dt - window_start).total_seconds())
        if window_seconds <= 0:
            continue

        # Expected transaction volume scaling with propensity and digital maturity
        # Effective tenure factor scales down volume for customers who signed up recently (< 90 days ago)
        tenure_factor = min(1.0, window_seconds / (history_days * 86400))
        lam = base_volume * (0.15 + 1.70 * nat_propensity) * (0.50 + 0.80 * dig_maturity) * tenure_factor
        n_txns = _poisson_draw(rng, lam)

        if n_txns == 0:
            continue

        # Channel probabilities driven by digital maturity
        # Higher digital maturity -> higher app share
        p_app = 0.20 + 0.70 * dig_maturity
        p_agent = (1.0 - p_app) * 0.55
        p_ussd = (1.0 - p_app) * 0.45

        # Transaction type probabilities driven by QR affinity and channels
        # QR share rises with qr_affinity
        qr_weight = 0.05 + 0.45 * qr_affinity
        merchant_weight = 0.12
        cash_in_weight = 0.20
        cash_out_weight = 0.18
        p2p_send_weight = 0.18
        p2p_recv_weight = 0.12
        bill_weight = 0.08
        recharge_weight = 0.07

        txn_type_choices = [
            "qr_pay",
            "merchant_pay",
            "cash_in",
            "cash_out",
            "p2p_send",
            "p2p_receive",
            "bill_pay",
            "recharge",
        ]
        txn_type_weights = [
            qr_weight,
            merchant_weight,
            cash_in_weight,
            cash_out_weight,
            p2p_send_weight,
            p2p_recv_weight,
            bill_weight,
            recharge_weight,
        ]

        # Generate each transaction
        for _ in range(n_txns):
            txn_id = f"TXN{global_txn_counter:010d}"
            global_txn_counter += 1

            # Event time: strictly before assigned_dt (at least 1 second prior)
            offset_sec = rng.randint(1, window_seconds)
            event_time = assigned_dt - timedelta(seconds=offset_sec)
            event_time_str = event_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Channel
            channel = rng.choices(["app", "agent", "ussd"], weights=[p_app, p_agent, p_ussd], k=1)[0]

            # Transaction type
            txn_type = rng.choices(txn_type_choices, weights=txn_type_weights, k=1)[0]

            # Direction and merchant category rules
            if txn_type in TXN_TYPES_INFLOW:
                direction = "in"
                merchant_category = None
            elif txn_type in TXN_TYPES_MERCHANT:
                direction = "out"
                merchant_category = rng.choice(MERCHANT_CATEGORIES)
                # QR pay and merchant pay are digital app transactions
                if txn_type == "qr_pay":
                    channel = "app"
            else:
                direction = "out"
                merchant_category = None

            # Amount in BDT (> 0 and <= 100,000)
            if txn_type in ["merchant_pay", "qr_pay"]:
                # Retail purchases: 50 to 5,000 BDT typical
                raw_amt = rng.expovariate(1 / 350.0) + 20.0
            elif txn_type in ["recharge", "bill_pay"]:
                raw_amt = rng.expovariate(1 / 200.0) + 20.0
            else:
                # Cash in / cash out / p2p: larger transfers
                raw_amt = rng.expovariate(1 / 1500.0) + 100.0

            amount_bdt = round(min(100000.0, max(10.0, raw_amt)), 2)

            txn_record = {
                "transaction_id": txn_id,
                "customer_id": cust_id,
                "event_time": event_time_str,
                "txn_type": txn_type,
                "amount_bdt": amount_bdt,
                "channel": channel,
                "merchant_category": merchant_category,
                "direction": direction,
            }
            all_transactions.append(txn_record)

    # Sort all transactions chronologically by event_time
    all_transactions.sort(key=lambda x: x["event_time"])
    return all_transactions
