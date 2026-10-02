"""Tests for outcome simulator and true uplift (potential outcomes) module."""

import json
from pathlib import Path
import sys
import jsonschema
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.assignment import assign_treatment
from campaignlift_data.campaigns import get_current_campaign
from campaignlift_data.config import load_world_config
from campaignlift_data.customers import generate_customers
from campaignlift_data.outcomes import (
    generate_outcomes_and_hidden_uplift,
)
from campaignlift_data.transactions import generate_transactions


@pytest.fixture
def outcome_schema():
    """Load canonical factual outcome schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "outcome.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def hidden_uplift_schema():
    """Load canonical hidden uplift schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "hidden_uplift.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_outcomes_and_hidden_uplift_schema_conformance(outcome_schema, hidden_uplift_schema):
    """Outcomes and hidden uplift records strictly conform to their respective JSON schemas."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)
    campaign = get_current_campaign()
    exposures, audit = assign_treatment(customers, txns, campaign=campaign)

    outcomes, hidden_uplifts = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
    )

    assert len(outcomes) == len(exposures), "Every eligible exposed customer gets an outcome"
    assert len(hidden_uplifts) == len(customers), "Every customer has potential outcomes evaluated"

    for o in outcomes:
        jsonschema.validate(instance=o, schema=outcome_schema)

    for h in hidden_uplifts:
        jsonschema.validate(instance=h, schema=hidden_uplift_schema)
        # Bounds on probabilities
        assert 0.01 <= h["p_y_control"] <= 0.99
        assert 0.01 <= h["p_y_treat"] <= 0.99
        assert -1.0 <= h["true_uplift"] <= 1.0


def test_hidden_uplift_has_both_positive_and_negative_uplift():
    """Synthetic causal world generates both positive and negative uplift (acceptance criteria)."""
    customers, latents = generate_customers(200, seed=42)
    txns = generate_transactions(customers, latents, seed=42)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign, seed=42)

    _, hidden_uplifts = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
        seed=42,
    )

    pos_uplifts = [h["true_uplift"] for h in hidden_uplifts if h["true_uplift"] > 0]
    neg_uplifts = [h["true_uplift"] for h in hidden_uplifts if h["true_uplift"] < 0]

    print(f"Positive uplift count: {len(pos_uplifts)}, Negative uplift count: {len(neg_uplifts)}")
    assert len(pos_uplifts) > 0, "World failed to produce any positive uplift"
    assert len(neg_uplifts) > 0, "World failed to produce any negative uplift (sleeping dogs)"


def test_outcome_consistency_with_y_transacted():
    """Outcome window counts and amounts must strictly follow y_transacted."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign)

    outcomes, _ = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
    )

    for o in outcomes:
        if o["y_transacted"] == 0:
            assert o["txn_count_window"] == 0
            assert o["txn_amount_window_bdt"] == 0.0
        else:
            assert o["txn_count_window"] >= 1
            assert o["txn_amount_window_bdt"] > 0.0


def test_no_forbidden_columns_leak_into_outcomes():
    """Verify that factual outcomes never leak latent variables, potential outcomes, or true uplift."""
    customers, latents = generate_customers(50)
    txns = generate_transactions(customers, latents)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign)

    outcomes, _ = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
    )

    forbidden_path = Path(__file__).resolve().parents[1] / "schemas" / "FORBIDDEN_TRAINING_COLUMNS.txt"
    with open(forbidden_path, "r", encoding="utf-8") as f:
        forbidden_cols = {line.strip() for line in f if line.strip() and not line.startswith("#")}

    for o in outcomes:
        for key in o.keys():
            assert key not in forbidden_cols, f"Forbidden column '{key}' leaked into factual outcomes!"


def test_determinism_two_runs_match():
    """Two simulation runs with identical seeds produce identical outcomes and hidden uplifts."""
    customers, latents = generate_customers(100, seed=123)
    txns = generate_transactions(customers, latents, seed=123)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign, seed=123)

    outcomes_1, hidden_1 = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
        seed=123,
    )

    outcomes_2, hidden_2 = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
        seed=123,
    )

    assert outcomes_1 == outcomes_2, "Two outcome simulation runs did not match"
    assert hidden_1 == hidden_2, "Two hidden uplift simulation runs did not match"


def test_negative_outcome_schema_rejection(outcome_schema):
    """Negative test: Inconsistent outcome records fail schema validation."""
    valid_base = {
        "customer_id": "C00000001",
        "campaign_id": "CMP2024_QR01",
        "y_transacted": 0,
        "txn_count_window": 0,
        "txn_amount_window_bdt": 0.0,
        "window_start": "2024-02-01T00:00:00Z",
        "window_end": "2024-02-15T00:00:00Z",
    }
    jsonschema.validate(instance=valid_base, schema=outcome_schema)

    # 1. y_transacted == 0 but positive count -> must fail
    bad_count = dict(valid_base, txn_count_window=2)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_count, schema=outcome_schema)

    # 2. y_transacted == 1 but zero amount -> must fail
    bad_zero_amount = dict(valid_base, y_transacted=1, txn_count_window=1, txn_amount_window_bdt=0.0)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_zero_amount, schema=outcome_schema)

    # 3. Invalid y_transacted enum (must be 0 or 1)
    bad_y = dict(valid_base, y_transacted=3)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_y, schema=outcome_schema)
