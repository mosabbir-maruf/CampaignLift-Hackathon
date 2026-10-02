"""CampaignLift Synthetic Data Generation Package.

Provides canonical world configuration loading and deterministic stage seeds
for customer, transaction, and campaign simulation.
"""

from .config import load_world_config
from .seeds import (
    STAGE_OFFSETS,
    get_stage_seeds,
    get_stage_seed,
)

__all__ = [
    "load_world_config",
    "STAGE_OFFSETS",
    "get_stage_seeds",
    "get_stage_seed",
]
