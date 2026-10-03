"""Tests for prior campaign exposure generator module."""

from datetime import date, timedelta
from pathlib import Path
import sys
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.campaigns import (
    DEFAULT_CAMPAIGN_START_DATE,
    get_current_campaign,
    get_prior_campaigns,
)
from campaignlift_data.config import load_world_config
from campaignlift_data.customers import generate_customers
from campaignlift_data.exposures import (
    compute_observed_fatigue_features,
    generate_prior_exposures,
)


def test_prior_dates_strictly_before_assigned_at():
    """All prior exposure dates are strictly before assigned_at and within 90-day history."""
    customers, latents = generate_customers(200)
    assigned_d = DEFAULT_CAMPAIGN_START_DATE
    history_start_d = assigned_d - timedelta(days=90)

    exposures = generate_prior_exposures(customers, latents, assigned_date=assigned_d)

    assert len(exposures) > 0, "No prior exposures generated"

    current_camp = get_current_campaign()
    modeled_id = current_camp["campaign_id"]

    for exp in exposures:
        exp_d = date.fromisoformat(exp["exposure_date"])
        # Must be strictly before assigned_date
        assert exp_d < assigned_d, f"Exposure date {exp_d} is >= assigned_date {assigned_d}"
        # Must be within 90-day window
        assert exp_d >= history_start_d, f"Exposure date {exp_d} is earlier than history start {history_start_d}"
        # Must NEVER be the modeled campaign
        assert exp["campaign_id"] != modeled_id, f"Modeled campaign {modeled_id} leaked into prior exposures"


def test_exposure_counts_differ_across_customers():
    """Prior exposure counts differ across customers on the fixture cohort."""
    customers, latents = generate_customers(200)
    exposures = generate_prior_exposures(customers, latents)

    # Count exposures per customer
    counts: dict[str, int] = {c["customer_id"]: 0 for c in customers}
    for exp in exposures:
        counts[exp["customer_id"]] += 1

    distinct_counts = set(counts.values())
    print(f"Distinct exposure counts observed: {sorted(distinct_counts)}")

    # Acceptance criteria: counts differ across customers
    assert len(distinct_counts) > 2, f"Expected varied counts, got only {distinct_counts}"
    # Verify bounds [0, 4]
    for cid, cnt in counts.items():
        assert 0 <= cnt <= 4, f"Customer {cid} count {cnt} out of bounds [0, 4]"


def test_negative_uplift_profile_has_higher_mean_exposures():
    """Customers in negative_uplift profile receive higher mean prior exposures."""
    customers, latents = generate_customers(500, seed=999)
    exposures = generate_prior_exposures(customers, latents, seed=999)

    counts: dict[str, int] = {c["customer_id"]: 0 for c in customers}
    for exp in exposures:
        counts[exp["customer_id"]] += 1

    latents_by_id = {l["customer_id"]: l for l in latents}

    neg_uplift_counts = [
        counts[cid]
        for cid, lat in latents_by_id.items()
        if lat["profile"] == "negative_uplift"
    ]
    other_counts = [
        counts[cid]
        for cid, lat in latents_by_id.items()
        if lat["profile"] != "negative_uplift"
    ]

    mean_neg = sum(neg_uplift_counts) / max(len(neg_uplift_counts), 1)
    mean_other = sum(other_counts) / max(len(other_counts), 1)

    print(f"Mean exposures: negative_uplift={mean_neg:.2f}, others={mean_other:.2f}")
    assert mean_neg > mean_other, (
        f"Expected negative_uplift mean ({mean_neg}) > others mean ({mean_other})"
    )


def test_compute_observed_fatigue_features():
    """Verify calculation of observed 30d, 90d touch counts and recency."""
    assigned_d = date(2024, 2, 1)
    cid = "C00000001"

    # Case 1: Customer with no prior exposures
    feat_zero = compute_observed_fatigue_features(cid, [], assigned_date=assigned_d)
    assert feat_zero["campaign_exposures_prior_30d"] == 0
    assert feat_zero["campaign_exposures_prior_90d"] == 0
    assert feat_zero["days_since_last_campaign"] == 999

    # Case 2: Customer with 2 exposures (one 10 days ago, one 45 days ago)
    mock_exps = [
        {
            "prior_exposure_id": "PEXP00000001",
            "customer_id": cid,
            "campaign_id": "CMP2024_QR00",
            "exposure_date": "2024-01-22",  # 10 days prior
            "channel": "push",
        },
        {
            "prior_exposure_id": "PEXP00000002",
            "customer_id": cid,
            "campaign_id": "CMP2023_REA01",
            "exposure_date": "2023-12-18",  # 45 days prior
            "channel": "in_app",
        },
    ]

    feat = compute_observed_fatigue_features(cid, mock_exps, assigned_date=assigned_d)
    assert feat["campaign_exposures_prior_30d"] == 1
    assert feat["campaign_exposures_prior_90d"] == 2
    assert feat["days_since_last_campaign"] == 10


def test_negative_exposure_date_at_or_after_assignment_fails():
    """Negative test: Deliberate exposure at or after assignment date is detected."""
    assigned_d = DEFAULT_CAMPAIGN_START_DATE

    def validate_exposure_date(exp_date_str: str):
        exp_d = date.fromisoformat(exp_date_str)
        if exp_d >= assigned_d:
            raise AssertionError(f"Leakage detected: prior exposure date {exp_d} >= {assigned_d}")

    with pytest.raises(AssertionError, match="Leakage detected"):
        validate_exposure_date("2024-02-01")

    with pytest.raises(AssertionError, match="Leakage detected"):
        validate_exposure_date("2024-02-05")

    # Positive control
    validate_exposure_date("2024-01-31")
