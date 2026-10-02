"""Tests for feature table builder module."""

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

from campaignlift_data.assignment import assign_treatment
from campaignlift_data.campaigns import get_current_campaign
from campaignlift_data.customers import generate_customers
from campaignlift_data.exposures import generate_prior_exposures
from campaignlift_data.features import (
    FORBIDDEN_COLUMNS,
    build_feature_table,
    compute_transaction_aggregates,
)
from campaignlift_data.outcomes import generate_outcomes_and_hidden_uplift
from campaignlift_data.transactions import generate_transactions


@pytest.fixture
def feature_schema():
    """Load canonical feature table schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "feature_table.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_feature_table_row_count_equals_exposure_count(feature_schema):
    """Row count of feature table strictly equals exposure count, and all rows validate against schema."""
    customers, latents = generate_customers(200)
    txns = generate_transactions(customers, latents)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign)
    prior_exps = generate_prior_exposures(customers, latents)
    outcomes, _ = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
    )

    feature_table = build_feature_table(
        customers=customers,
        transactions=txns,
        prior_exposures=prior_exps,
        exposures=exposures,
        outcomes=outcomes,
        campaign=campaign,
    )

    # Acceptance criteria 1: Row count equals exposure count
    assert len(feature_table) == len(exposures), (
        f"Feature row count ({len(feature_table)}) does not match exposure count ({len(exposures)})"
    )

    # Acceptance criteria 2: Schema validation
    for row in feature_table:
        jsonschema.validate(instance=row, schema=feature_schema)


def test_forbidden_column_intersection_is_empty():
    """Forbidden column intersection is strictly empty across all rows in the feature table."""
    customers, latents = generate_customers(100)
    txns = generate_transactions(customers, latents)
    campaign = get_current_campaign()
    exposures, _ = assign_treatment(customers, txns, campaign=campaign)
    prior_exps = generate_prior_exposures(customers, latents)
    outcomes, _ = generate_outcomes_and_hidden_uplift(
        customers=customers,
        customer_latents=latents,
        transactions=txns,
        exposures=exposures,
        campaign=campaign,
    )

    feature_table = build_feature_table(
        customers=customers,
        transactions=txns,
        prior_exposures=prior_exps,
        exposures=exposures,
        outcomes=outcomes,
        campaign=campaign,
    )

    forbidden_path = Path(__file__).resolve().parents[1] / "schemas" / "FORBIDDEN_TRAINING_COLUMNS.txt"
    with open(forbidden_path, "r", encoding="utf-8") as f:
        file_forbidden_cols = {line.strip() for line in f if line.strip() and not line.startswith("#")}

    all_forbidden = FORBIDDEN_COLUMNS | file_forbidden_cols

    for row in feature_table:
        intersection = set(row.keys()) & all_forbidden
        assert len(intersection) == 0, f"Forbidden columns present in feature row: {intersection}"


def test_transaction_exactly_at_assigned_at_is_excluded():
    """A transaction occurring exactly at assigned_at is strictly excluded from historical aggregates."""
    assigned_dt = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Create dummy transactions:
    # 1 second before assigned_at -> should be included
    # exactly at assigned_at -> must be EXCLUDED
    # 1 second after assigned_at -> must be EXCLUDED
    txns = [
        {
            "transaction_id": "TXN_BEFORE",
            "customer_id": "C00000001",
            "event_time": "2024-01-31T23:59:59Z",
            "txn_type": "qr_pay",
            "amount_bdt": 100.0,
            "channel": "app",
        },
        {
            "transaction_id": "TXN_EXACT",
            "customer_id": "C00000001",
            "event_time": "2024-02-01T00:00:00Z",
            "txn_type": "merchant_pay",
            "amount_bdt": 500.0,
            "channel": "app",
        },
        {
            "transaction_id": "TXN_AFTER",
            "customer_id": "C00000001",
            "event_time": "2024-02-01T00:00:01Z",
            "txn_type": "cash_in",
            "amount_bdt": 1000.0,
            "channel": "agent",
        },
    ]

    aggs = compute_transaction_aggregates(txns, assigned_dt=assigned_dt)

    # Acceptance criteria: TXN_EXACT and TXN_AFTER are excluded
    assert aggs["txn_count_90d"] == 1, f"Expected exactly 1 valid txn, got {aggs['txn_count_90d']}"
    assert aggs["txn_amount_90d_bdt"] == 100.0, f"Expected amount 100.0, got {aggs['txn_amount_90d_bdt']}"
    assert aggs["qr_txn_share_90d"] == 1.0


def test_negative_feature_schema_rejection_on_forbidden_column(feature_schema):
    """Negative test: Injecting forbidden columns causes schema failure."""
    valid_row = {
        "customer_id": "C00000001",
        "campaign_id": "CMP2024_QR01",
        "tenure_days": 120,
        "age_band": "25-34",
        "region_code": "DHK",
        "kyc_level": "verified",
        "acquisition_channel": "app",
        "txn_count_30d": 5,
        "txn_count_90d": 15,
        "txn_amount_30d_bdt": 1500.0,
        "txn_amount_90d_bdt": 4500.0,
        "qr_txn_share_90d": 0.20,
        "cashout_share_90d": 0.10,
        "merchant_pay_share_90d": 0.15,
        "days_since_last_txn": 3,
        "avg_ticket_90d_bdt": 300.0,
        "app_channel_share_90d": 0.80,
        "campaign_exposures_prior_30d": 1,
        "campaign_exposures_prior_90d": 2,
        "days_since_last_campaign": 12,
        "objective": "qr_adoption",
        "offer_type": "flat_cashback",
        "incentive_value": 20.0,
        "incentive_cost_bdt": 20.0,
        "treatment": 1,
        "y_transacted": 1,
    }
    jsonschema.validate(instance=valid_row, schema=feature_schema)

    # Injecting true_uplift -> schema has additionalProperties: false, must fail!
    bad_row = dict(valid_row, true_uplift=0.15)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_row, schema=feature_schema)

    # Injecting offer_fatigue -> must fail!
    bad_row2 = dict(valid_row, offer_fatigue=0.5)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_row2, schema=feature_schema)
