"""Campaign definition and prior campaign generator for CampaignLift causal world.

Emits the single modeled current campaign from configuration plus prior-campaign
stubs used to stamp historical exposures in the 90-day history window prior to assignment.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Union

from .config import load_world_config

DEFAULT_CAMPAIGN_START_DATE = date(2024, 2, 1)


def get_current_campaign(
    config: Optional[Dict[str, Any]] = None,
    assigned_date: Optional[Union[date, str]] = None,
) -> Dict[str, Any]:
    """Build the single current modeled campaign for evaluation and optimization.

    Args:
        config: Optional loaded world.yaml configuration dictionary.
        assigned_date: Campaign launch/assignment date (default 2024-02-01).

    Returns:
        Dict conforming to campaign.schema.json.
    """
    if config is None:
        config = load_world_config()

    if assigned_date is None:
        start_d = DEFAULT_CAMPAIGN_START_DATE
    elif isinstance(assigned_date, str):
        start_d = date.fromisoformat(assigned_date)
    else:
        start_d = assigned_date

    # Objective comes from eligibility configuration (demo objective)
    demo_objective = config.get("eligibility", {}).get("default_demo_objective", "qr_adoption")

    # Outcome window days from timeline config
    outcome_window_days = config.get("timeline", {}).get("outcome_window_days", 14)

    # Unit cost in BDT comes from config/campaign specs, never derived from uplift or ROI
    incentive_cost_bdt = float(config.get("campaign", {}).get("incentive_cost_bdt", 20.0))
    incentive_value = float(config.get("campaign", {}).get("incentive_value", 20.0))
    offer_type = config.get("campaign", {}).get("offer_type", "flat_cashback")
    channel = config.get("campaign", {}).get("channel", "in_app")
    campaign_id = config.get("campaign", {}).get("campaign_id", "CMP2024_QR01")
    campaign_name = config.get("campaign", {}).get(
        "campaign_name", "Q1 2024 QR Merchant Pay Booster"
    )

    end_d = start_d + timedelta(days=outcome_window_days - 1)

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "objective": demo_objective,
        "offer_type": offer_type,
        "incentive_value": incentive_value,
        "incentive_cost_bdt": incentive_cost_bdt,
        "channel": channel,
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "outcome_window_days": int(outcome_window_days),
    }


def get_prior_campaigns(
    config: Optional[Dict[str, Any]] = None,
    assigned_date: Optional[Union[date, str]] = None,
) -> List[Dict[str, Any]]:
    """Build prior campaign stubs used to stamp historical exposures in the past.

    All prior campaign end dates are strictly before assigned_date.

    Args:
        config: Optional loaded world.yaml configuration dictionary.
        assigned_date: Campaign launch/assignment date (default 2024-02-01).

    Returns:
        List of campaign dicts conforming to campaign.schema.json,
        ordered chronologically by start_date.
    """
    if config is None:
        config = load_world_config()

    if assigned_date is None:
        assigned_d = DEFAULT_CAMPAIGN_START_DATE
    elif isinstance(assigned_date, str):
        assigned_d = date.fromisoformat(assigned_date)
    else:
        assigned_d = assigned_date

    # Define prior campaign stubs relative to assigned_date to guarantee all end_date < assigned_date
    # Offset days from assigned_date: (start_days_before, duration_days)
    prior_stubs_spec = [
        {
            "campaign_id": "CMP2023_ACT01",
            "campaign_name": "Q4 2023 New User Welcome",
            "objective": "activation",
            "offer_type": "flat_cashback",
            "incentive_value": 15.0,
            "incentive_cost_bdt": 15.0,
            "channel": "sms",
            "start_days_before": 88,
            "duration_days": 14,
        },
        {
            "campaign_id": "CMP2023_RET01",
            "campaign_name": "Late Nov Active User Reward",
            "objective": "retention",
            "offer_type": "fee_waiver",
            "incentive_value": 0.0,
            "incentive_cost_bdt": 5.0,
            "channel": "push",
            "start_days_before": 73,
            "duration_days": 14,
        },
        {
            "campaign_id": "CMP2023_REA01",
            "campaign_name": "Winter Reactivation Campaign",
            "objective": "reactivation",
            "offer_type": "pct_cashback",
            "incentive_value": 10.0,
            "incentive_cost_bdt": 25.0,
            "channel": "in_app",
            "start_days_before": 53,
            "duration_days": 14,
        },
        {
            "campaign_id": "CMP2024_NEW01",
            "campaign_name": "New Year 2024 App Challenge",
            "objective": "activation",
            "offer_type": "flat_cashback",
            "incentive_value": 20.0,
            "incentive_cost_bdt": 20.0,
            "channel": "in_app",
            "start_days_before": 30,
            "duration_days": 14,
        },
        {
            "campaign_id": "CMP2024_QR00",
            "campaign_name": "January Early QR Pilot",
            "objective": "qr_adoption",
            "offer_type": "flat_cashback",
            "incentive_value": 10.0,
            "incentive_cost_bdt": 10.0,
            "channel": "push",
            "start_days_before": 17,
            "duration_days": 14,
        },
    ]

    priors: List[Dict[str, Any]] = []
    for spec in prior_stubs_spec:
        start_date = assigned_d - timedelta(days=spec["start_days_before"])
        end_date = start_date + timedelta(days=spec["duration_days"] - 1)

        # Enforce end_date strictly before assigned_date
        assert end_date < assigned_d, (
            f"Prior campaign {spec['campaign_id']} end_date {end_date} must be < assigned_date {assigned_d}"
        )

        priors.append({
            "campaign_id": spec["campaign_id"],
            "campaign_name": spec["campaign_name"],
            "objective": spec["objective"],
            "offer_type": spec["offer_type"],
            "incentive_value": float(spec["incentive_value"]),
            "incentive_cost_bdt": float(spec["incentive_cost_bdt"]),
            "channel": spec["channel"],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "outcome_window_days": int(spec["duration_days"]),
        })

    # Sort chronologically by start_date
    priors.sort(key=lambda c: c["start_date"])
    return priors
