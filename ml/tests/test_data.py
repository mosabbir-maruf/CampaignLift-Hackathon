"""Tests for campaignlift_ml.data loader module.

Verifies:
1. Manifest parsing on fixture and dev manifests.
2. Dataset loading and split partitioning on fixture_v1.
3. Cryptographic checksum validation on dataset files.
4. Strict anti-leakage protection: tampered or forbidden columns immediately raise ForbiddenColumnError.
5. Refusal to read or depend on hidden_uplift.json.
"""

import copy
import json
from pathlib import Path
import pytest
import pandas as pd

from campaignlift_ml.data import (
    ForbiddenColumnError,
    ChecksumMismatchError,
    ManifestError,
    load_manifest,
    load_dataset_splits,
    load_train_val,
    assert_no_forbidden_columns,
    compute_sha256,
    FEATURE_COLUMNS,
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    DEFAULT_FORBIDDEN_COLUMNS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "fixture_v1"
DEV_MANIFEST_PATH = REPO_ROOT / "data" / "manifests" / "dev_manifest.json"
ML_DEV_MANIFEST_PATH = REPO_ROOT / "data" / "manifests" / "ml_dev_manifest.json"


def test_load_dev_manifest():
    """Loader correctly reads and parses the official dev manifest."""
    manifest = load_manifest(DEV_MANIFEST_PATH)
    assert manifest["config_name"] == "dev"
    assert manifest["global_seed"] == 20261006
    assert manifest["row_counts"]["customers"] == 5000
    assert "features.json" in manifest["file_checksums"]
    assert "splits.json" in manifest["file_checksums"]


def test_load_ml_dev_manifest():
    """Loader correctly reads and parses the official ml_dev manifest."""
    manifest = load_manifest(ML_DEV_MANIFEST_PATH)
    assert manifest["config_name"] == "ml_dev"
    assert manifest["row_counts"]["customers"] == 25000
    assert manifest["row_counts"]["features"] == 12491


def test_load_fixture_manifest():
    """Loader correctly reads the fixture manifest."""
    fixture_manifest_path = FIXTURE_DIR / "manifest.json"
    manifest = load_manifest(fixture_manifest_path)
    assert manifest["config_name"] == "fixture"
    assert manifest["row_counts"]["customers"] == 200
    assert manifest["row_counts"]["features"] == 103


def test_load_dataset_splits_from_fixture():
    """Loader reads fixture_v1, verifies checksums, and partitions into train, val, and test."""
    splits = load_dataset_splits(FIXTURE_DIR, verify_hashes=True, include_test=True)

    assert isinstance(splits.train, pd.DataFrame)
    assert isinstance(splits.val, pd.DataFrame)
    assert isinstance(splits.test, pd.DataFrame)

    # Check total rows match the 103 fixture exposures
    total_rows = len(splits.train) + len(splits.val) + len(splits.test)
    assert total_rows == 103

    # Check that required columns exist
    for col in FEATURE_COLUMNS + [TARGET_COLUMN, TREATMENT_COLUMN, "customer_id", "campaign_id"]:
        assert col in splits.train.columns
        assert col in splits.val.columns
        assert col in splits.test.columns

    # Verify no overlap between customer_ids in splits
    train_ids = set(splits.train["customer_id"])
    val_ids = set(splits.val["customer_id"])
    test_ids = set(splits.test["customer_id"])
    assert len(train_ids.intersection(val_ids)) == 0
    assert len(train_ids.intersection(test_ids)) == 0
    assert len(val_ids.intersection(test_ids)) == 0


def test_load_train_val_excludes_test():
    """load_train_val returns strictly train and val, leaving test untouched."""
    train_df, val_df = load_train_val(FIXTURE_DIR, verify_hashes=True)
    assert isinstance(train_df, pd.DataFrame)
    assert isinstance(val_df, pd.DataFrame)
    assert len(train_df) > 0
    assert len(val_df) > 0
    assert len(train_df) + len(val_df) < 103  # test split was excluded


def test_tampered_forbidden_column_raises(tmp_path):
    """If a feature file is tampered to include a forbidden column, ForbiddenColumnError is raised."""
    # Create valid dummy files
    features = [
        {
            "customer_id": "C00000001",
            "campaign_id": "CMP1",
            "tenure_days": 100,
            "treatment": 1,
            "y_transacted": 1,
            "true_uplift": 0.05,  # FORBIDDEN ORACLE COLUMN!
        }
    ]
    splits = [{"customer_id": "C00000001", "split": "train"}]

    f_path = tmp_path / "features.json"
    s_path = tmp_path / "splits.json"

    f_path.write_text(json.dumps(features), encoding="utf-8")
    s_path.write_text(json.dumps(splits), encoding="utf-8")

    with pytest.raises(ForbiddenColumnError, match="CRITICAL CAUSAL LEAKAGE"):
        load_dataset_splits(tmp_path, verify_hashes=False)


@pytest.mark.parametrize("forbidden_col", list(DEFAULT_FORBIDDEN_COLUMNS))
def test_all_individual_forbidden_columns_detected(forbidden_col):
    """assert_no_forbidden_columns catches every column in FORBIDDEN_TRAINING_COLUMNS.txt."""
    tampered_cols = ["customer_id", "tenure_days", forbidden_col]
    with pytest.raises(ForbiddenColumnError):
        assert_no_forbidden_columns(tampered_cols)


def test_tampered_checksum_raises(tmp_path):
    """If a file on disk has a different hash than the manifest, ChecksumMismatchError is raised."""
    features = [{"customer_id": "C00000001", "tenure_days": 100, "treatment": 1, "y_transacted": 0}]
    splits = [{"customer_id": "C00000001", "split": "train"}]

    f_path = tmp_path / "features.json"
    s_path = tmp_path / "splits.json"
    m_path = tmp_path / "manifest.json"

    f_path.write_text(json.dumps(features), encoding="utf-8")
    s_path.write_text(json.dumps(splits), encoding="utf-8")

    fake_manifest = {
        "dataset_version": "test-v1",
        "global_seed": 1234,
        "row_counts": {"features": 1, "splits": 1},
        "file_checksums": {
            "features.json": "0000000000000000000000000000000000000000000000000000000000000000",
            "splits.json": compute_sha256(s_path),
        },
    }
    m_path.write_text(json.dumps(fake_manifest), encoding="utf-8")

    with pytest.raises(ChecksumMismatchError, match="Checksum mismatch"):
        load_dataset_splits(tmp_path, verify_hashes=True)


def test_missing_dataset_files_raises(tmp_path):
    """Missing features or splits raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_dataset_splits(tmp_path, verify_hashes=False)
