"""Tests for customer generator module validating uniqueness, enums, dates, and seed stability."""

from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
import jsonschema
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.customers import (
    DEFAULT_CAMPAIGN_START_DATE,
    generate_customers,
)


def test_customer_generation_determinism():
    """Generating 200 customers twice with the same seed yields identical outputs."""
    customers_1, latents_1 = generate_customers(200)
    customers_2, latents_2 = generate_customers(200)

    assert len(customers_1) == 200
    assert len(latents_1) == 200
    assert customers_1 == customers_2
    assert latents_1 == latents_2

    # Check deterministic IDs
    id_pattern = re.compile(r"^C\d{8}$")
    for i, c in enumerate(customers_1, start=1):
        assert c["customer_id"] == f"C{i:08d}"
        assert id_pattern.match(c["customer_id"])


def test_customer_schema_validation():
    """All generated customer rows validate against customer.schema.json."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "customer.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    customers, _ = generate_customers(200)
    for c in customers:
        jsonschema.validate(instance=c, schema=schema)


def test_no_forbidden_columns_in_customer_output():
    """Customer output must never contain latent variables, profile names, or forbidden columns."""
    forbidden_path = Path(__file__).resolve().parents[1] / "schemas" / "FORBIDDEN_TRAINING_COLUMNS.txt"
    with open(forbidden_path, "r", encoding="utf-8") as f:
        forbidden_cols = set(line.strip() for line in f if line.strip())

    forbidden_cols.add("profile")

    expected_allowed_keys = {
        "customer_id",
        "signup_date",
        "age_band",
        "region_code",
        "kyc_level",
        "acquisition_channel",
    }

    customers, _ = generate_customers(200)
    for c in customers:
        c_keys = set(c.keys())
        assert c_keys == expected_allowed_keys
        assert c_keys.isdisjoint(forbidden_cols), f"Forbidden column found in customer: {c_keys & forbidden_cols}"


def test_latent_separation_and_bounds():
    """Latents are returned separately to caller with all 6 variables within [0, 1]."""
    required_latents = {
        "natural_transaction_propensity",
        "qr_affinity",
        "price_sensitivity",
        "campaign_sensitivity",
        "digital_maturity",
        "offer_fatigue",
    }
    valid_profiles = {"sure_thing", "persuadable", "weak_responder", "negative_uplift"}

    customers, latents = generate_customers(200)

    for c, lat in zip(customers, latents):
        assert c["customer_id"] == lat["customer_id"]
        assert lat["profile"] in valid_profiles

        for var in required_latents:
            val = lat[var]
            assert 0.0 <= val <= 1.0, f"Latent {var}={val} out of bounds for {lat['customer_id']}"


def test_customer_uniqueness_enums_and_signup_dates():
    """Verify customer_id uniqueness, valid enums, and signup_date strictly before campaign start."""
    customers, _ = generate_customers(500)

    # 1. Uniqueness of customer_id
    customer_ids = [c["customer_id"] for c in customers]
    assert len(customer_ids) == len(set(customer_ids)), "Duplicate customer_id detected"

    # 2. Strict enum membership according to data plan
    allowed_age_bands = {"18-24", "25-34", "35-44", "45-54", "55+"}
    allowed_region_codes = {"DHK", "CTG", "SYL", "RAJ", "KHU", "BAR", "RAN", "MYM"}
    allowed_kyc_levels = {"limited", "verified"}
    allowed_acquisition_channels = {"app", "agent", "referral"}

    for c in customers:
        assert c["age_band"] in allowed_age_bands, f"Invalid age_band: {c['age_band']}"
        assert c["region_code"] in allowed_region_codes, f"Invalid region_code: {c['region_code']}"
        assert c["kyc_level"] in allowed_kyc_levels, f"Invalid kyc_level: {c['kyc_level']}"
        assert c["acquisition_channel"] in allowed_acquisition_channels, f"Invalid acquisition_channel: {c['acquisition_channel']}"

        # 3. Signup date strictly before campaign start
        signup_dt = date.fromisoformat(c["signup_date"])
        assert signup_dt < DEFAULT_CAMPAIGN_START_DATE, (
            f"Customer signup_date {signup_dt} is not before campaign start {DEFAULT_CAMPAIGN_START_DATE}"
        )


def test_seed_variation_changes_attributes():
    """Verify that different seeds produce different customer attributes, while identical seeds match."""
    customers_seed_a, _ = generate_customers(100, seed=12345)
    customers_seed_a_repeat, _ = generate_customers(100, seed=12345)
    customers_seed_b, _ = generate_customers(100, seed=99999)

    # Same seed matches exactly
    assert customers_seed_a == customers_seed_a_repeat

    # Different seed produces different demographic attributes
    assert customers_seed_a != customers_seed_b

    # At least some attributes must differ
    diff_count = sum(
        1 for ca, cb in zip(customers_seed_a, customers_seed_b)
        if (ca["age_band"], ca["region_code"], ca["kyc_level"], ca["acquisition_channel"], ca["signup_date"]) !=
           (cb["age_band"], cb["region_code"], cb["kyc_level"], cb["acquisition_channel"], cb["signup_date"])
    )
    assert diff_count > 0, "Changing seed did not alter customer attributes"
