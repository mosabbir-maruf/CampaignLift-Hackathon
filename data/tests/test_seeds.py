"""Tests for world configuration loader and deterministic stage seed derivation."""

import pytest
import sys
from pathlib import Path

# Add data/src to sys.path so campaignlift_data can be imported directly
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.config import load_world_config
from campaignlift_data.seeds import (
    STAGE_OFFSETS,
    get_stage_seeds,
    get_stage_seed,
)


def test_load_world_config_success():
    """Verify that canonical world.yaml loads and contains global_seed."""
    config = load_world_config()
    assert "global_seed" in config
    assert config["global_seed"] == 20261006


def test_load_world_config_rejects_missing_global_seed(tmp_path):
    """Verify that config loader raises ValueError if global_seed is missing."""
    bad_yaml = tmp_path / "bad_world.yaml"
    bad_yaml.write_text("timeline:\n  history_days: 90\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required 'global_seed'"):
        load_world_config(bad_yaml)


def test_stage_seeds_match_data_plan():
    """Verify that all six stage seeds equal global_seed + documented offset."""
    config = load_world_config()
    global_seed = config["global_seed"]
    assert global_seed == 20261006

    expected_seeds = {
        "customers": 20261007,
        "transactions": 20261008,
        "prior_exposures": 20261009,
        "treatment_assignment": 20261010,
        "outcome_noise_and_bernoulli": 20261011,
        "split": 20261012,
    }

    seeds = get_stage_seeds(config)
    assert seeds == expected_seeds

    # Test individual get_stage_seed
    for stage, expected in expected_seeds.items():
        assert get_stage_seed(stage, config=config) == expected
        assert get_stage_seed(stage, global_seed=global_seed) == expected


def test_stage_offsets_completeness():
    """Verify all 6 canonical stages exist in STAGE_OFFSETS."""
    expected_stages = {
        "customers",
        "transactions",
        "prior_exposures",
        "treatment_assignment",
        "outcome_noise_and_bernoulli",
        "split",
    }
    assert set(STAGE_OFFSETS.keys()) == expected_stages


def test_invalid_stage_name_raises_key_error():
    """Verify that requesting an unknown stage raises KeyError."""
    with pytest.raises(KeyError, match="Unknown stage 'invalid_stage'"):
        get_stage_seed("invalid_stage")
