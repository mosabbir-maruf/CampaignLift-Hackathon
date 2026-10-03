"""Deterministic stage seed calculation for CampaignLift causal generation stages."""

from typing import Any, Dict, Optional
from .config import load_world_config

# Deterministic stage seed offsets
STAGE_OFFSETS: Dict[str, int] = {
    "customers": 1,
    "transactions": 2,
    "prior_exposures": 3,
    "treatment_assignment": 4,
    "outcome_noise_and_bernoulli": 5,
    "split": 6,
}


def get_stage_seeds(
    config: Optional[Dict[str, Any]] = None,
    global_seed: Optional[int] = None,
) -> Dict[str, int]:
    """Calculate the six deterministic stage seeds as global_seed + documented stage offset.

    Args:
        config: Optional loaded configuration dictionary. If None and global_seed is None,
                load_world_config() is called.
        global_seed: Optional explicit global seed integer overriding config.

    Returns:
        Dictionary mapping each of the 6 stages to its exact integer seed.
    """
    if global_seed is None:
        if config is None:
            config = load_world_config()
        global_seed = config["global_seed"]

    return {
        stage: int(global_seed) + offset
        for stage, offset in STAGE_OFFSETS.items()
    }


def get_stage_seed(
    stage: str,
    config: Optional[Dict[str, Any]] = None,
    global_seed: Optional[int] = None,
) -> int:
    """Return the deterministic integer seed for a single named generation stage.

    Args:
        stage: Stage name (one of: customers, transactions, prior_exposures,
               treatment_assignment, outcome_noise_and_bernoulli, split).
        config: Optional loaded configuration dictionary.
        global_seed: Optional explicit global seed.

    Returns:
        Integer seed for the requested stage.

    Raises:
        KeyError: If stage is not one of the documented stages.
    """
    if stage not in STAGE_OFFSETS:
        raise KeyError(
            f"Unknown stage '{stage}'. Must be one of: {list(STAGE_OFFSETS.keys())}"
        )

    seeds = get_stage_seeds(config=config, global_seed=global_seed)
    return seeds[stage]
