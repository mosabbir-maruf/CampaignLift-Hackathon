"""Prior campaign exposure generator for CampaignLift causal world.

Assigns historical campaign touches (0 to 4 per customer) inside the 90-day pre-assignment
window. Exposure counts drive observed fatigue features and are shifted higher for
customers in the negative_uplift profile.
"""

from datetime import date, datetime, timedelta
import random
from typing import Any, Dict, List, Optional, Union

from .campaigns import DEFAULT_CAMPAIGN_START_DATE, get_current_campaign, get_prior_campaigns
from .config import load_world_config
from .seeds import get_stage_seed


def generate_prior_exposures(
    customers: List[Dict[str, Any]],
    customer_latents: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
    assigned_date: Optional[Union[date, str]] = None,
) -> List[Dict[str, Any]]:
    """Generate historical campaign exposure records for a cohort of customers.

    Args:
        customers: List of customer dicts (must have customer_id and signup_date).
        customer_latents: List of corresponding latent dicts (with profile and offer_fatigue).
        config: Optional loaded world.yaml configuration dictionary.
        seed: Optional integer seed. Defaults to stage seed 'prior_exposures'.
        assigned_date: Campaign assignment date (default 2024-02-01). All exposures occur strictly before this.

    Returns:
        List of prior exposure records with keys:
            prior_exposure_id, customer_id, campaign_id, exposure_date, channel.
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("prior_exposures", config=config)

    rng = random.Random(seed)

    if assigned_date is None:
        assigned_d = DEFAULT_CAMPAIGN_START_DATE
    elif isinstance(assigned_date, str):
        assigned_d = date.fromisoformat(assigned_date)
    else:
        assigned_d = assigned_date

    history_days = config.get("timeline", {}).get("history_days", 90)
    history_start_d = assigned_d - timedelta(days=history_days)

    # Load prior campaign catalog (guaranteed end_date < assigned_d)
    prior_campaigns = get_prior_campaigns(config=config, assigned_date=assigned_d)
    current_campaign = get_current_campaign(config=config, assigned_date=assigned_d)
    current_campaign_id = current_campaign["campaign_id"]

    # Pre-index latents by customer_id
    latents_by_id = {lat["customer_id"]: lat for lat in customer_latents}

    all_exposures: List[Dict[str, Any]] = []
    global_counter = 1

    # Weights for exposure counts [0, 1, 2, 3, 4]
    # Standard profile: moderate touch frequency (mean ~ 1.5)
    standard_weights = [0.22, 0.35, 0.25, 0.14, 0.04]
    # Negative uplift profile: shifted toward higher touch frequency (mean ~ 2.8)
    negative_uplift_weights = [0.03, 0.10, 0.25, 0.37, 0.25]

    count_choices = [0, 1, 2, 3, 4]

    for cust in customers:
        cust_id = cust["customer_id"]
        lat = latents_by_id.get(cust_id)
        if not lat:
            continue

        profile = lat.get("profile", "")
        signup_d = date.fromisoformat(cust["signup_date"])

        # Customer observation window: [max(signup_date, history_start_date), assigned_date - 1 day]
        window_start = max(signup_d, history_start_d)
        window_days = (assigned_d - window_start).days
        if window_days <= 0:
            continue

        # Select distribution based on profile
        if profile == "negative_uplift":
            raw_count = rng.choices(count_choices, weights=negative_uplift_weights, k=1)[0]
        else:
            raw_count = rng.choices(count_choices, weights=standard_weights, k=1)[0]

        # Scale down count if customer joined recently (< 90 days ago)
        tenure_fraction = min(1.0, window_days / float(history_days))
        effective_count = min(raw_count, max(0, int(round(raw_count * tenure_fraction))))

        if effective_count == 0:
            continue

        # Ensure we don't sample more dates than available days in window
        num_to_sample = min(effective_count, window_days)
        # Sample distinct offset days from assigned_date (offset 1 means assigned_date - 1 day)
        offset_days = rng.sample(range(1, window_days + 1), k=num_to_sample)
        offset_days.sort(reverse=True)  # Chronological order

        for offset in offset_days:
            exp_date = assigned_d - timedelta(days=offset)

            # Never assign the current modeled campaign
            chosen_camp = rng.choice(prior_campaigns)
            assert chosen_camp["campaign_id"] != current_campaign_id, (
                "Modeled campaign must never appear as prior exposure"
            )

            exp_record = {
                "prior_exposure_id": f"PEXP{global_counter:08d}",
                "customer_id": cust_id,
                "campaign_id": chosen_camp["campaign_id"],
                "exposure_date": exp_date.isoformat(),
                "channel": chosen_camp["channel"],
            }
            all_exposures.append(exp_record)
            global_counter += 1

    # Sort exposures chronologically by exposure_date
    all_exposures.sort(key=lambda x: (x["exposure_date"], x["customer_id"]))
    return all_exposures


def compute_observed_fatigue_features(
    customer_id: str,
    exposures: List[Dict[str, Any]],
    assigned_date: Optional[Union[date, str]] = None,
) -> Dict[str, int]:
    """Compute observed prior exposure counts and recency at assigned_date.

    Args:
        customer_id: Identifier of the customer.
        exposures: List of prior exposure records for this customer (or all exposures).
        assigned_date: Campaign assignment date (default 2024-02-01).

    Returns:
        Dict containing:
            campaign_exposures_prior_30d: Count of exposures within 30 days prior.
            campaign_exposures_prior_90d: Count of exposures within 90 days prior.
            days_since_last_campaign: Days elapsed since latest exposure, or 999 if none.
    """
    if assigned_date is None:
        assigned_d = DEFAULT_CAMPAIGN_START_DATE
    elif isinstance(assigned_date, str):
        assigned_d = date.fromisoformat(assigned_date)
    else:
        assigned_d = assigned_date

    d30_cutoff = assigned_d - timedelta(days=30)
    d90_cutoff = assigned_d - timedelta(days=90)

    cust_exps = [e for e in exposures if e["customer_id"] == customer_id]

    prior_30d = 0
    prior_90d = 0
    latest_date: Optional[date] = None

    for e in cust_exps:
        exp_d = date.fromisoformat(e["exposure_date"])
        if exp_d < assigned_d:
            if exp_d >= d90_cutoff:
                prior_90d += 1
            if exp_d >= d30_cutoff:
                prior_30d += 1
            if latest_date is None or exp_d > latest_date:
                latest_date = exp_d

    if latest_date is None:
        days_since = 999
    else:
        days_since = (assigned_d - latest_date).days

    return {
        "campaign_exposures_prior_30d": prior_30d,
        "campaign_exposures_prior_90d": prior_90d,
        "days_since_last_campaign": days_since,
    }
