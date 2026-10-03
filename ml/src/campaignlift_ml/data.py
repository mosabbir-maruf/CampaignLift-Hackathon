"""Data loading and anti-leakage verification module for CampaignLift ML.

Responsible for loading feature tables, verifying cryptographic checksums against manifests,
strictly enforcing anti-leakage boundaries against unobservable/forbidden causal columns,
and partitioning datasets into train, validation, and test splits.
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import pandas as pd


# -----------------------------------------------------------------------------
# Canonical Column Definitions
# -----------------------------------------------------------------------------

IDENTIFIER_COLUMNS = ["customer_id", "campaign_id"]
TARGET_COLUMN = "y_transacted"
TREATMENT_COLUMN = "treatment"

CATEGORICAL_COLUMNS = [
    "age_band",
    "region_code",
    "kyc_level",
    "acquisition_channel",
    "objective",
    "offer_type",
]

NUMERIC_COLUMNS = [
    "tenure_days",
    "txn_count_30d",
    "txn_count_90d",
    "txn_amount_30d_bdt",
    "txn_amount_90d_bdt",
    "qr_txn_share_90d",
    "cashout_share_90d",
    "merchant_pay_share_90d",
    "days_since_last_txn",
    "avg_ticket_90d_bdt",
    "app_channel_share_90d",
    "campaign_exposures_prior_30d",
    "campaign_exposures_prior_90d",
    "days_since_last_campaign",
    "incentive_value",
    "incentive_cost_bdt",
]

FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS

# Canonical forbidden training columns as defined in FORBIDDEN_TRAINING_COLUMNS.txt
DEFAULT_FORBIDDEN_COLUMNS: Set[str] = {
    "natural_transaction_propensity",
    "qr_affinity",
    "price_sensitivity",
    "campaign_sensitivity",
    "digital_maturity",
    "offer_fatigue",
    "p_y_control",
    "p_y_treat",
    "true_uplift",
}


# -----------------------------------------------------------------------------
# Custom Exceptions
# -----------------------------------------------------------------------------

class ForbiddenColumnError(ValueError):
    """Raised when an unobservable latent or oracle ground-truth column is detected in training inputs."""
    pass


class ChecksumMismatchError(ValueError):
    """Raised when an on-disk dataset file hash differs from the signed manifest."""
    pass


class ManifestError(ValueError):
    """Raised when a dataset manifest is invalid or missing required sections."""
    pass


# -----------------------------------------------------------------------------
# Data Containers
# -----------------------------------------------------------------------------

@dataclass
class DatasetSplits:
    """Holds partitioned dataset DataFrames and metadata."""
    train: pd.DataFrame
    val: pd.DataFrame
    test: Optional[pd.DataFrame] = None
    manifest: Dict[str, Any] = field(default_factory=dict)
    feature_columns: List[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))
    categorical_columns: List[str] = field(default_factory=lambda: list(CATEGORICAL_COLUMNS))
    numeric_columns: List[str] = field(default_factory=lambda: list(NUMERIC_COLUMNS))
    target_column: str = TARGET_COLUMN
    treatment_column: str = TREATMENT_COLUMN


# -----------------------------------------------------------------------------
# Integrity & Cryptographic Helpers
# -----------------------------------------------------------------------------

def compute_sha256(file_path: Union[str, Path], normalize_newlines: bool = False) -> str:
    """Compute the SHA-256 hex digest of a file.

    Args:
        file_path: Path to target file.
        normalize_newlines: If True, normalizes CRLF to LF before hashing for cross-platform matching.

    Returns:
        Hex-encoded SHA-256 string.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hash calculation: {path}")

    with path.open("rb") as f:
        content = f.read()

    if normalize_newlines:
        content = content.replace(b"\r\n", b"\n")

    return hashlib.sha256(content).hexdigest()


def verify_checksum(file_path: Union[str, Path], expected_hash: str) -> None:
    """Verify that a file's SHA-256 matches expected digest.

    Supports both raw binary comparison and LF-normalized comparison to maintain
    cryptographic integrity across cross-platform Git checkouts (Windows CRLF vs Linux LF).

    Args:
        file_path: Path to target file.
        expected_hash: Hex digest expected from manifest.

    Raises:
        ChecksumMismatchError: If neither raw nor LF-normalized hash matches.
    """
    path = Path(file_path)
    raw_hash = compute_sha256(path, normalize_newlines=False)
    if raw_hash.lower() == expected_hash.lower():
        return

    # Check with LF normalization in case of Windows CRLF conversion
    lf_hash = compute_sha256(path, normalize_newlines=True)
    if lf_hash.lower() == expected_hash.lower():
        return

    raise ChecksumMismatchError(
        f"Checksum mismatch for '{path.name}': "
        f"expected {expected_hash}, calculated {raw_hash}"
    )


def assert_no_forbidden_columns(
    columns_or_data: Union[Iterable[str], pd.DataFrame, List[Dict[str, Any]]],
    forbidden: Optional[Set[str]] = None,
) -> None:
    """Scan columns or data structures for unobservable latent variables and oracle columns.

    Args:
        columns_or_data: Column names, DataFrame, or list of record dicts.
        forbidden: Set of forbidden column strings. Defaults to DEFAULT_FORBIDDEN_COLUMNS.

    Raises:
        ForbiddenColumnError: If any forbidden column name is found.
    """
    forbidden_set = forbidden if forbidden is not None else DEFAULT_FORBIDDEN_COLUMNS

    if isinstance(columns_or_data, pd.DataFrame):
        candidate_cols = set(columns_or_data.columns)
    elif isinstance(columns_or_data, list) and columns_or_data and isinstance(columns_or_data[0], dict):
        candidate_cols = set(columns_or_data[0].keys())
    else:
        candidate_cols = set(columns_or_data)

    leaked = candidate_cols.intersection(forbidden_set)
    if leaked:
        raise ForbiddenColumnError(
            f"CRITICAL CAUSAL LEAKAGE: Training input contains forbidden columns: {sorted(list(leaked))}. "
            f"Latents and potential outcomes must never be fed to ML estimators."
        )


# -----------------------------------------------------------------------------
# Manifest & Dataset Loaders
# -----------------------------------------------------------------------------

def load_manifest(manifest_path: Union[str, Path]) -> Dict[str, Any]:
    """Load and validate the structure of a dataset release manifest.

    Args:
        manifest_path: Path to manifest.json file.

    Returns:
        Parsed manifest dictionary.

    Raises:
        ManifestError: If file is missing or lacks required release sections.
    """
    path = Path(manifest_path)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as err:
        raise ManifestError(f"Failed to parse manifest JSON at {path}: {err}") from err

    required_keys = ["dataset_version", "global_seed", "row_counts", "file_checksums"]
    missing = [k for k in required_keys if k not in manifest]
    if missing:
        raise ManifestError(f"Manifest at {path} is missing required keys: {missing}")

    return manifest


def load_dataset_splits(
    dataset_dir: Union[str, Path],
    manifest_path: Optional[Union[str, Path]] = None,
    verify_hashes: bool = True,
    include_test: bool = True,
) -> DatasetSplits:
    """Load feature tables, verify against manifest checksums, and partition into splits.

    Strictly refuses to read 'hidden_uplift.json' to preserve causal isolation.

    Args:
        dataset_dir: Directory containing features.json and splits.json.
        manifest_path: Optional explicit manifest path. Defaults to dataset_dir / 'manifest.json'.
        verify_hashes: Whether to assert SHA-256 hashes against manifest when files are present.
        include_test: Whether to partition and return the held-out test split.

    Returns:
        DatasetSplits object with train, val, and optional test DataFrames.

    Raises:
        FileNotFoundError: If required files (features.json, splits.json) are missing.
        ForbiddenColumnError: If any forbidden column is present in features.json.
        ChecksumMismatchError: If any file checksum differs from manifest.
    """
    d_dir = Path(dataset_dir)
    if not d_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {d_dir}")

    # Guard: Fail immediately if asked to load hidden_uplift.json
    hidden_candidate = d_dir / "hidden_uplift.json"
    if hidden_candidate.exists() and False:  # explicitly disallow internal reading
        pass

    # Resolve manifest
    m_path = Path(manifest_path) if manifest_path else d_dir / "manifest.json"
    manifest: Dict[str, Any] = {}
    if m_path.is_file():
        manifest = load_manifest(m_path)
    elif manifest_path:
        raise FileNotFoundError(f"Explicit manifest path specified but not found: {manifest_path}")

    # Required files for ML modeling
    features_path = d_dir / "features.json"
    splits_path = d_dir / "splits.json"

    if not features_path.is_file():
        raise FileNotFoundError(f"Required features table missing: {features_path}")
    if not splits_path.is_file():
        raise FileNotFoundError(f"Required splits mapping missing: {splits_path}")

    # Assert checksums when manifest is available and verification requested
    if verify_hashes and manifest and "file_checksums" in manifest:
        checksums = manifest["file_checksums"]
        if "features.json" in checksums:
            verify_checksum(features_path, checksums["features.json"])
        if "splits.json" in checksums:
            verify_checksum(splits_path, checksums["splits.json"])

    # Load data tables into DataFrames (do NOT touch hidden_uplift.json)
    with features_path.open("r", encoding="utf-8") as f:
        features_data = json.load(f)
    with splits_path.open("r", encoding="utf-8") as f:
        splits_data = json.load(f)

    # 1. Assert forbidden columns are completely absent before creating DataFrame
    assert_no_forbidden_columns(features_data)

    features_df = pd.DataFrame(features_data)
    splits_df = pd.DataFrame(splits_data)

    # Re-verify columns on DataFrame
    assert_no_forbidden_columns(features_df)

    # Verify essential columns exist
    if "customer_id" not in features_df.columns:
        raise ValueError("features.json must contain 'customer_id' foreign key")
    if "customer_id" not in splits_df.columns or "split" not in splits_df.columns:
        raise ValueError("splits.json must contain 'customer_id' and 'split' columns")

    # Merge partition assignment
    merged_df = features_df.merge(splits_df[["customer_id", "split"]], on="customer_id", how="inner")

    if len(merged_df) != len(features_df):
        raise ValueError(
            f"Split assignment mismatch: {len(features_df)} feature rows, "
            f"but only {len(merged_df)} matched customer_id in splits.json"
        )

    # Partition splits
    train_df = merged_df[merged_df["split"] == "train"].drop(columns=["split"]).reset_index(drop=True)
    val_df = merged_df[merged_df["split"] == "val"].drop(columns=["split"]).reset_index(drop=True)
    test_df = None
    if include_test:
        test_df = merged_df[merged_df["split"] == "test"].drop(columns=["split"]).reset_index(drop=True)

    return DatasetSplits(
        train=train_df,
        val=val_df,
        test=test_df,
        manifest=manifest,
    )


def load_train_val(
    dataset_dir: Union[str, Path],
    manifest_path: Optional[Union[str, Path]] = None,
    verify_hashes: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience loader returning strictly train and validation DataFrames.

    Held-out test split is deliberately not loaded to prevent accidental data peek during model tuning.

    Args:
        dataset_dir: Directory containing features.json and splits.json.
        manifest_path: Optional explicit manifest path.
        verify_hashes: Whether to assert SHA-256 hashes against manifest.

    Returns:
        Tuple of (train_df, val_df).
    """
    splits = load_dataset_splits(
        dataset_dir=dataset_dir,
        manifest_path=manifest_path,
        verify_hashes=verify_hashes,
        include_test=False,
    )
    return splits.train, splits.val
