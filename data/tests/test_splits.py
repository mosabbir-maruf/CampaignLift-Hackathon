"""Tests for dataset split module."""

from pathlib import Path
import sys
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.assignment import assign_treatment
from campaignlift_data.campaigns import get_current_campaign
from campaignlift_data.customers import generate_customers
from campaignlift_data.exposures import generate_prior_exposures
from campaignlift_data.features import build_feature_table
from campaignlift_data.outcomes import generate_outcomes_and_hidden_uplift
from campaignlift_data.splits import (
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VAL,
    assign_customer_splits,
    generate_splits_table,
    hash_customer_to_split,
    partition_feature_table,
)
from campaignlift_data.transactions import generate_transactions


def test_split_shares_within_two_points_on_dev_size():
    """Shares are within 2 percentage points of 60/20/20 on dev size (5,000 customers)."""
    # 5,000 customer IDs
    cids = [f"C{i:08d}" for i in range(1, 5001)]
    splits = assign_customer_splits(cids)

    n_total = len(cids)
    assert n_total == 5000

    train_cids = {cid for cid, s in splits.items() if s == SPLIT_TRAIN}
    val_cids = {cid for cid, s in splits.items() if s == SPLIT_VAL}
    test_cids = {cid for cid, s in splits.items() if s == SPLIT_TEST}

    # Mutual exclusivity (intersection of ids is empty)
    assert train_cids.isdisjoint(val_cids), "Train and val have overlapping customer IDs"
    assert train_cids.isdisjoint(test_cids), "Train and test have overlapping customer IDs"
    assert val_cids.isdisjoint(test_cids), "Val and test have overlapping customer IDs"

    # Union covers all customers
    assert train_cids | val_cids | test_cids == set(cids)

    share_train = len(train_cids) / n_total
    share_val = len(val_cids) / n_total
    share_test = len(test_cids) / n_total

    print(f"Observed shares: train={share_train:.4f} (target 0.60), val={share_val:.4f} (target 0.20), test={share_test:.4f} (target 0.20)")

    # Acceptance criteria: Within 2 percentage points of 60/20/20
    assert 0.58 <= share_train <= 0.62, f"Train share {share_train:.4f} outside [0.58, 0.62]"
    assert 0.18 <= share_val <= 0.22, f"Val share {share_val:.4f} outside [0.18, 0.22]"
    assert 0.18 <= share_test <= 0.22, f"Test share {share_test:.4f} outside [0.18, 0.22]"


def test_partition_feature_table_disjoint_and_complete():
    """Partitioning feature table produces disjoint views with zero customer duplication."""
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

    partitions = partition_feature_table(feature_table)

    train_rows = partitions[SPLIT_TRAIN]
    val_rows = partitions[SPLIT_VAL]
    test_rows = partitions[SPLIT_TEST]

    # Total rows preserved
    assert len(train_rows) + len(val_rows) + len(test_rows) == len(feature_table)

    train_ids = {r["customer_id"] for r in train_rows}
    val_ids = {r["customer_id"] for r in val_rows}
    test_ids = {r["customer_id"] for r in test_rows}

    # Mutual exclusivity
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)


def test_split_determinism():
    """Hashing customer IDs is completely deterministic across multiple calls with the same seed."""
    cids = [f"C{i:08d}" for i in range(1, 201)]
    run_1 = assign_customer_splits(cids, seed=20261012)
    run_2 = assign_customer_splits(cids, seed=20261012)
    assert run_1 == run_2

    # Changing seed alters assignments
    run_other = assign_customer_splits(cids, seed=99999999)
    assert run_1 != run_other


def test_generate_splits_table_format():
    """Generate splits table returns list of dicts with customer_id and split."""
    cids = ["C00000001", "C00000002", "C00000003"]
    records = generate_splits_table(cids)

    assert len(records) == 3
    for r in records:
        assert "customer_id" in r
        assert "split" in r
        assert r["split"] in {SPLIT_TRAIN, SPLIT_VAL, SPLIT_TEST}
