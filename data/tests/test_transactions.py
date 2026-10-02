"""Tests for transaction generator module."""

from datetime import datetime, timezone
import json
from pathlib import Path
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
from campaignlift_data.transactions import generate_transactions


def test_transactions_timing_strictly_before_assignment():
    """All generated transaction event times are strictly before campaign assignment."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)

    assert len(txns) > 0, "No transactions were generated"

    assigned_dt = datetime.combine(
        DEFAULT_CAMPAIGN_START_DATE,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    for t in txns:
        event_dt = datetime.fromisoformat(t["event_time"].replace("Z", "+00:00"))
        # Must be strictly before assignment
        assert event_dt < assigned_dt, f"Transaction {t['transaction_id']} event_time {event_dt} is >= assignment {assigned_dt}"


def test_transactions_schema_validation():
    """All transactions conform to data/schemas/transaction.schema.json."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "transaction.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    customers, latents = generate_customers(100)
    txns = generate_transactions(customers, latents)

    assert len(txns) > 0
    # Validate each transaction against schema
    for t in txns:
        jsonschema.validate(instance=t, schema=schema)


def test_high_propensity_produces_higher_mean_count_than_low_propensity():
    """A high-propensity fixture customer has a higher mean count than a low-propensity one across a fixed seed."""
    # Synthesize two cohorts: high propensity vs low propensity
    high_prop_cust = []
    high_prop_lat = []
    low_prop_cust = []
    low_prop_lat = []

    for i in range(1, 51):
        cid_hi = f"C1{i:07d}"
        cid_lo = f"C2{i:07d}"

        high_prop_cust.append({
            "customer_id": cid_hi,
            "signup_date": "2023-01-01",
            "age_band": "25-34",
            "region_code": "DHK",
            "kyc_level": "verified",
            "acquisition_channel": "app",
        })
        high_prop_lat.append({
            "customer_id": cid_hi,
            "profile": "sure_thing",
            "natural_transaction_propensity": 0.90,
            "qr_affinity": 0.50,
            "price_sensitivity": 0.20,
            "campaign_sensitivity": 0.10,
            "digital_maturity": 0.70,
            "offer_fatigue": 0.10,
        })

        low_prop_cust.append({
            "customer_id": cid_lo,
            "signup_date": "2023-01-01",
            "age_band": "25-34",
            "region_code": "DHK",
            "kyc_level": "limited",
            "acquisition_channel": "agent",
        })
        low_prop_lat.append({
            "customer_id": cid_lo,
            "profile": "weak_responder",
            "natural_transaction_propensity": 0.10,
            "qr_affinity": 0.50,
            "price_sensitivity": 0.20,
            "campaign_sensitivity": 0.10,
            "digital_maturity": 0.70,
            "offer_fatigue": 0.10,
        })

    txns_hi = generate_transactions(high_prop_cust, high_prop_lat, seed=42)
    txns_lo = generate_transactions(low_prop_cust, low_prop_lat, seed=42)

    mean_hi = len(txns_hi) / len(high_prop_cust)
    mean_lo = len(txns_lo) / len(low_prop_cust)

    print(f"Mean count high propensity: {mean_hi:.2f}, low propensity: {mean_lo:.2f}")
    assert mean_hi > mean_lo * 2.0, (
        f"Expected high-propensity mean ({mean_hi}) to be significantly higher than low-propensity mean ({mean_lo})"
    )


def test_qr_share_increases_with_qr_affinity():
    """Customers with high QR affinity generate higher QR transaction share."""
    cust_hi, lat_hi, cust_lo, lat_lo = [], [], [], []

    for i in range(1, 41):
        cid_h = f"C3{i:07d}"
        cid_l = f"C4{i:07d}"
        base_c = {
            "signup_date": "2023-01-01",
            "age_band": "25-34",
            "region_code": "DHK",
            "kyc_level": "verified",
            "acquisition_channel": "app",
        }
        base_l = {
            "profile": "persuadable",
            "natural_transaction_propensity": 0.70,
            "price_sensitivity": 0.50,
            "campaign_sensitivity": 0.80,
            "digital_maturity": 0.80,
            "offer_fatigue": 0.10,
        }

        cust_hi.append(dict(base_c, customer_id=cid_h))
        lat_hi.append(dict(base_l, customer_id=cid_h, qr_affinity=0.95))

        cust_lo.append(dict(base_c, customer_id=cid_l))
        lat_lo.append(dict(base_l, customer_id=cid_l, qr_affinity=0.05))

    txns_hi = generate_transactions(cust_hi, lat_hi, seed=123)
    txns_lo = generate_transactions(cust_lo, lat_lo, seed=123)

    qr_hi = sum(1 for t in txns_hi if t["txn_type"] == "qr_pay") / max(len(txns_hi), 1)
    qr_lo = sum(1 for t in txns_lo if t["txn_type"] == "qr_pay") / max(len(txns_lo), 1)

    print(f"QR share high affinity: {qr_hi:.4f}, low affinity: {qr_lo:.4f}")
    assert qr_hi > qr_lo, f"Expected qr_share_hi ({qr_hi}) > qr_share_lo ({qr_lo})"
