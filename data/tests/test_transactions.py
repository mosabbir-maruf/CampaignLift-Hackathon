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


def test_merchant_category_rules_on_generated_transactions():
    """Verify merchant_category and direction rules across all generated transactions."""
    customers, latents = generate_customers(150)
    txns = generate_transactions(customers, latents)

    assert len(txns) > 0
    for t in txns:
        txn_type = t["txn_type"]
        cat = t["merchant_category"]
        direction = t["direction"]
        amount = t["amount_bdt"]

        # Amount bounds
        assert 0 < amount <= 100000.0, f"Transaction amount out of bounds: {amount}"

        # Merchant category rule: required for merchant_pay and qr_pay, null otherwise
        if txn_type in ["merchant_pay", "qr_pay"]:
            assert cat is not None, f"Expected merchant_category for {txn_type}, got None"
            assert cat in ["grocery", "transport", "food", "telecom", "other"]
            assert direction == "out"
        else:
            assert cat is None, f"Expected null merchant_category for {txn_type}, got {cat}"

        # Inflow vs outflow direction rule
        if txn_type in ["cash_in", "p2p_receive"]:
            assert direction == "in"
        else:
            assert direction == "out"


def test_negative_cutoff_detection():
    """Negative test: Deliberately bad rows at or after assigned_at must fail the cutoff check."""
    assigned_dt = datetime.combine(
        DEFAULT_CAMPAIGN_START_DATE,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    def check_cutoff(event_time_str: str):
        event_dt = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
        if event_dt >= assigned_dt:
            raise AssertionError(f"Leakage detected: event_time {event_dt} >= assigned_at {assigned_dt}")

    # Case 1: event_time exactly at assignment time (2024-02-01T00:00:00Z)
    with pytest.raises(AssertionError, match="Leakage detected"):
        check_cutoff("2024-02-01T00:00:00Z")

    # Case 2: event_time 1 second into campaign window (2024-02-01T00:00:01Z)
    with pytest.raises(AssertionError, match="Leakage detected"):
        check_cutoff("2024-02-01T00:00:01Z")

    # Case 3: event_time well after assignment (e.g., 2024-02-15T12:00:00Z)
    with pytest.raises(AssertionError, match="Leakage detected"):
        check_cutoff("2024-02-15T12:00:00Z")

    # Positive control: 1 second prior to assignment is valid
    check_cutoff("2024-01-31T23:59:59Z")


def test_negative_merchant_category_schema_rejection():
    """Negative test: Deliberately bad rows violating merchant_category rules must fail schema validation."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "transaction.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    valid_base = {
        "transaction_id": "TXN0000000001",
        "customer_id": "C00000001",
        "event_time": "2024-01-15T10:30:00Z",
        "txn_type": "merchant_pay",
        "amount_bdt": 250.0,
        "channel": "app",
        "merchant_category": "grocery",
        "direction": "out",
    }
    # Verify baseline is valid
    jsonschema.validate(instance=valid_base, schema=schema)

    # 1. merchant_pay missing merchant_category (set to null) -> must fail
    bad_merchant_pay = dict(valid_base, merchant_category=None)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_merchant_pay, schema=schema)

    # 2. cash_in with merchant_category set -> must fail
    bad_cash_in = dict(
        valid_base,
        txn_type="cash_in",
        direction="in",
        merchant_category="grocery",
    )
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_cash_in, schema=schema)

    # 3. p2p_send with invalid direction "in" -> must fail
    bad_p2p = dict(
        valid_base,
        txn_type="p2p_send",
        direction="in",
        merchant_category=None,
    )
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_p2p, schema=schema)

    # 4. amount_bdt <= 0 or > 100,000 -> must fail
    bad_amount_zero = dict(valid_base, amount_bdt=0.0)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_amount_zero, schema=schema)

    bad_amount_over = dict(valid_base, amount_bdt=100000.50)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_amount_over, schema=schema)

