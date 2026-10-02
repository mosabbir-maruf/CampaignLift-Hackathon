"""Tests for customer generator module."""

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

from campaignlift_data.customers import generate_customers


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
