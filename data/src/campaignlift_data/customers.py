"""Customer generator module for CampaignLift synthetic causal world.

Draws customer profiles from configured population mixtures, samples latent parameters,
and maps them to observable customer demographics without leaking latent variables into
the customer output.
"""

from datetime import date, datetime, timedelta
import random
from typing import Any, Dict, List, Optional, Tuple

from .config import load_world_config
from .seeds import get_stage_seed

# Canonical reference date for synthetic campaigns
DEFAULT_CAMPAIGN_START_DATE = date(2024, 2, 1)

# Demographic distribution weights (synthetic Bangladesh MFS representative)
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_BAND_WEIGHTS = [0.28, 0.38, 0.20, 0.10, 0.04]

REGION_CODES = ["DHK", "CTG", "SYL", "RAJ", "KHU", "BAR", "RAN", "MYM"]
REGION_WEIGHTS = [0.42, 0.20, 0.08, 0.08, 0.08, 0.05, 0.05, 0.04]

ACQUISITION_CHANNELS = ["app", "agent", "referral"]


def generate_customers(
    count: int,
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
    campaign_start: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate synthetic customers and their unobservable latent profiles.

    Args:
        count: Number of customer records to generate.
        config: Optional loaded world.yaml configuration dictionary.
        seed: Optional integer seed for customer generation. Defaults to stage seed.
        campaign_start: Optional campaign assignment start date for tenure calculation.

    Returns:
        A tuple of (customers, customer_latents):
            - customers: List of customer dicts strictly adhering to customer.schema.json.
                         Contains static attributes only; NO latent variables or profile names.
            - customer_latents: List of dicts containing customer_id, profile, and the 6 latents,
                                intended exclusively for internal oracle / simulation evaluation.
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("customers", config=config)

    rng = random.Random(seed)

    campaign_date = campaign_start or DEFAULT_CAMPAIGN_START_DATE

    # Extract profiles and share targets from world.yaml
    latent_profiles_cfg = config.get("latent_profiles", {})
    if not latent_profiles_cfg:
        raise ValueError("world.yaml is missing required 'latent_profiles' block")

    profile_names = list(latent_profiles_cfg.keys())
    profile_weights = [latent_profiles_cfg[name]["share_target"] for name in profile_names]

    customers: List[Dict[str, Any]] = []
    latents: List[Dict[str, Any]] = []

    for idx in range(1, count + 1):
        # 1. Deterministic customer identifier: C + 8 digits
        customer_id = f"C{idx:08d}"

        # 2. Sample latent profile from mixture
        selected_profile = rng.choices(profile_names, weights=profile_weights, k=1)[0]
        profile_def = latent_profiles_cfg[selected_profile]
        ranges = profile_def["ranges"]

        # 3. Sample the six latent parameters within profile bounds
        nat_propensity = round(rng.uniform(ranges["natural_transaction_propensity"][0], ranges["natural_transaction_propensity"][1]), 4)
        qr_affinity = round(rng.uniform(ranges["qr_affinity"][0], ranges["qr_affinity"][1]), 4)
        price_sens = round(rng.uniform(ranges["price_sensitivity"][0], ranges["price_sensitivity"][1]), 4)
        camp_sens = round(rng.uniform(ranges["campaign_sensitivity"][0], ranges["campaign_sensitivity"][1]), 4)
        dig_maturity = round(rng.uniform(ranges["digital_maturity"][0], ranges["digital_maturity"][1]), 4)
        offer_fatigue = round(rng.uniform(ranges["offer_fatigue"][0], ranges["offer_fatigue"][1]), 4)

        # Record latent record (strictly kept separate from customer frame)
        latent_record = {
            "customer_id": customer_id,
            "profile": selected_profile,
            "natural_transaction_propensity": nat_propensity,
            "qr_affinity": qr_affinity,
            "price_sensitivity": price_sens,
            "campaign_sensitivity": camp_sens,
            "digital_maturity": dig_maturity,
            "offer_fatigue": offer_fatigue,
        }
        latents.append(latent_record)

        # 4. Generate static demographic attributes
        # Account tenure: ~15% activation-eligible (tenure <= 30d), remaining up to 730d
        if rng.random() < 0.15:
            tenure_days = rng.randint(1, 30)
        else:
            tenure_days = rng.randint(31, 730)

        signup_date = (campaign_date - timedelta(days=tenure_days)).isoformat()

        age_band = rng.choices(AGE_BANDS, weights=AGE_BAND_WEIGHTS, k=1)[0]
        region_code = rng.choices(REGION_CODES, weights=REGION_WEIGHTS, k=1)[0]

        # Higher digital maturity slightly increases probability of app acquisition & verified KYC
        app_weight = 0.40 + (0.45 * dig_maturity)
        channel_weights = [app_weight, 0.40 * (1.0 - app_weight * 0.5), 0.30 * (1.0 - app_weight * 0.5)]
        acquisition_channel = rng.choices(ACQUISITION_CHANNELS, weights=channel_weights, k=1)[0]

        verified_prob = 0.50 + (0.40 * dig_maturity)
        kyc_level = "verified" if rng.random() < verified_prob else "limited"

        # 5. Customer observable record (matches customer.schema.json exactly)
        customer_record = {
            "customer_id": customer_id,
            "signup_date": signup_date,
            "age_band": age_band,
            "region_code": region_code,
            "kyc_level": kyc_level,
            "acquisition_channel": acquisition_channel,
        }
        customers.append(customer_record)

    return customers, latents
