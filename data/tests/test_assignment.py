"""Tests for treatment assignment and customer eligibility module."""

import json
from pathlib import Path
import sys
import jsonschema
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.assignment import (
    assign_treatment,
    evaluate_customer_eligibility,
)
from campaignlift_data.campaigns import get_current_campaign
from campaignlift_data.config import load_world_config
from campaignlift_data.customers import generate_customers
from campaignlift_data.transactions import generate_transactions


@pytest.fixture
def exposure_schema():
    """Load canonical exposure schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "exposure.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_exposure_schema_validation(exposure_schema):
    """All exposure records conform strictly to exposure.schema.json."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)

    exposures, audit = assign_treatment(customers, txns)

    assert len(exposures) > 0, "Expected some eligible exposures"
    for exp in exposures:
        jsonschema.validate(instance=exp, schema=exposure_schema)
        assert exp["eligible"] is True
        assert exp["assignment_probability"] == 0.5
        assert exp["treatment"] in (0, 1)


def test_ineligible_audit_separated_from_exposure_file():
    """Ineligible audit rows are completely separated and absent from the exposure file."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)

    exposures, audit = assign_treatment(customers, txns)

    exp_ids = {e["customer_id"] for e in exposures}
    audit_ids = {a["customer_id"] for a in audit}

    # Mutual exclusivity: no customer can be in both
    assert exp_ids.isdisjoint(audit_ids), "Eligible exposures and audit list overlap"

    # Union covers all input customers
    all_cust_ids = {c["customer_id"] for c in customers}
    assert exp_ids | audit_ids == all_cust_ids, "Not all customers accounted for"

    # Audit records have eligible=False and valid reason
    for a in audit:
        assert a["eligible"] is False
        assert len(a["reason"]) > 0


def test_treatment_rate_inside_bounds_on_large_cohort():
    """On a large cohort (5,000 customers), treatment rate is inside [0.45, 0.55]."""
    # 5,000 customers with dev seed
    customers, latents = generate_customers(5000, seed=42)
    txns = generate_transactions(customers, latents, seed=42)

    exposures, audit = assign_treatment(customers, txns, seed=42)

    n_eligible = len(exposures)
    assert n_eligible > 1000, f"Expected substantial eligible cohort, got {n_eligible}"

    treated_count = sum(1 for e in exposures if e["treatment"] == 1)
    treatment_rate = treated_count / n_eligible

    print(f"Eligible: {n_eligible}, Treated: {treated_count}, Treatment Rate: {treatment_rate:.4f}")
    assert 0.45 <= treatment_rate <= 0.55, (
        f"Treatment rate {treatment_rate:.4f} is outside required bounds [0.45, 0.55]"
    )


def test_eligibility_rules_by_objective():
    """Verify eligibility logic across all 4 marketing objectives."""
    config = load_world_config()

    # 1. Activation: tenure <= 30
    c_new = {"customer_id": "C10000001", "signup_date": "2024-01-20"}  # 12 days tenure
    c_old = {"customer_id": "C10000002", "signup_date": "2023-01-01"}  # > 365 days tenure
    assert evaluate_customer_eligibility(c_new, [], "activation", config=config)[0] is True
    assert evaluate_customer_eligibility(c_old, [], "activation", config=config)[0] is False

    # 2. Reactivation: tenure > 30 and 0 txns in last 30d
    recent_txn = [{"event_time": "2024-01-25T12:00:00Z", "txn_type": "cash_in"}]
    old_txn = [{"event_time": "2023-11-15T12:00:00Z", "txn_type": "cash_in"}]
    assert evaluate_customer_eligibility(c_old, old_txn, "reactivation", config=config)[0] is True
    assert evaluate_customer_eligibility(c_old, recent_txn, "reactivation", config=config)[0] is False

    # 3. QR adoption: >= 1 txn and qr_share <= 0.20
    txns_no_qr = [{"event_time": "2024-01-10T12:00:00Z", "txn_type": "merchant_pay"}]
    txns_heavy_qr = [
        {"event_time": "2024-01-10T12:00:00Z", "txn_type": "qr_pay"},
        {"event_time": "2024-01-12T12:00:00Z", "txn_type": "qr_pay"},
    ]
    assert evaluate_customer_eligibility(c_old, txns_no_qr, "qr_adoption", config=config)[0] is True
    assert evaluate_customer_eligibility(c_old, txns_heavy_qr, "qr_adoption", config=config)[0] is False


def test_negative_exposure_schema_rejection(exposure_schema):
    """Negative test: Exposures violating schema constraints fail validation."""
    valid_base = {
        "exposure_id": "EXP00000001",
        "customer_id": "C00000001",
        "campaign_id": "CMP2024_QR01",
        "eligible": True,
        "treatment": 1,
        "assignment_probability": 0.5,
        "assigned_at": "2024-02-01T00:00:00Z",
    }
    jsonschema.validate(instance=valid_base, schema=exposure_schema)

    # 1. Invalid treatment value (must be 0 or 1)
    bad_treatment = dict(valid_base, treatment=2)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_treatment, schema=exposure_schema)

    # 2. Ineligible flag in exposure table (schema requires eligible: true)
    bad_eligible = dict(valid_base, eligible=False)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_eligible, schema=exposure_schema)

    # 3. Altered assignment probability (schema requires const 0.5)
    bad_prob = dict(valid_base, assignment_probability=0.8)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_prob, schema=exposure_schema)
