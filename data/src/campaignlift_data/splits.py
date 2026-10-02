"""Dataset split module for CampaignLift synthetic causal world.

Assigns customers deterministically to train (60%), val (20%), and test (20%)
by hashing customer_id with the split seed. Never moves or stratifies rows on true uplift.
Partitions feature tables and generates split mappings without duplicating any customer.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .config import load_world_config
from .seeds import get_stage_seed

SPLIT_TRAIN = "train"
SPLIT_VAL = "val"
SPLIT_TEST = "test"
VALID_SPLITS: Set[str] = {SPLIT_TRAIN, SPLIT_VAL, SPLIT_TEST}


def hash_customer_to_split(customer_id: str, seed: int) -> str:
    """Deterministically assign a customer to train, val, or test using SHA-256 hash.

    Ratios:
        train: 60% [0, 5999]
        val:   20% [6000, 7999]
        test:  20% [8000, 9999]

    Args:
        customer_id: The canonical customer_id string (e.g. 'C00000001').
        seed: The integer split seed.

    Returns:
        One of 'train', 'val', 'test'.
    """
    key = f"{customer_id}_{seed}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    bucket = int(digest[:8], 16) % 10000

    if bucket < 6000:
        return SPLIT_TRAIN
    elif bucket < 8000:
        return SPLIT_VAL
    else:
        return SPLIT_TEST


def assign_customer_splits(
    customer_ids: List[str],
    seed: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Assign a cohort of customer IDs to train, val, or test splits.

    Args:
        customer_ids: List of customer_id strings.
        seed: Optional split seed. Defaults to stage seed 'split'.
        config: Optional world.yaml configuration dict.

    Returns:
        Dictionary mapping customer_id -> split name ('train', 'val', 'test').
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("split", config=config)

    return {cid: hash_customer_to_split(cid, seed) for cid in customer_ids}


def partition_feature_table(
    feature_rows: List[Dict[str, Any]],
    seed: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Partition a list of feature rows into disjoint train, val, and test subsets.

    Args:
        feature_rows: List of feature table records conforming to feature_table.schema.json.
        seed: Optional split seed.
        config: Optional configuration dict.

    Returns:
        Dictionary with keys 'train', 'val', 'test', containing partitioned feature rows.
    """
    if config is None:
        config = load_world_config()

    if seed is None:
        seed = get_stage_seed("split", config=config)

    partitions: Dict[str, List[Dict[str, Any]]] = {
        SPLIT_TRAIN: [],
        SPLIT_VAL: [],
        SPLIT_TEST: [],
    }

    for row in feature_rows:
        cid = row["customer_id"]
        split = hash_customer_to_split(cid, seed)
        partitions[split].append(row)

    return partitions


def generate_splits_table(
    customer_ids: List[str],
    seed: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Generate a split column record list without duplicating any customer.

    Args:
        customer_ids: List of customer_id strings.
        seed: Optional split seed.
        config: Optional configuration dict.

    Returns:
        List of records: [{'customer_id': 'C00000001', 'split': 'train'}, ...]
    """
    mapping = assign_customer_splits(customer_ids, seed=seed, config=config)
    return [{"customer_id": cid, "split": split} for cid, split in mapping.items()]
