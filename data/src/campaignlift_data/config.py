"""Configuration loader for CampaignLift causal world simulation."""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml


def get_default_config_path() -> Path:
    """Return the canonical path to data/config/world.yaml."""
    # File is in data/src/campaignlift_data/config.py -> parents[2] is data/
    base_data_dir = Path(__file__).resolve().parents[2]
    return base_data_dir / "config" / "world.yaml"


def load_world_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load world.yaml and enforce required configuration invariants.

    Args:
        config_path: Optional path to world.yaml. Defaults to data/config/world.yaml.

    Returns:
        Loaded configuration dictionary.

    Raises:
        FileNotFoundError: If the specified or default config file does not exist.
        ValueError: If 'global_seed' is missing or null.
    """
    path = Path(config_path) if config_path is not None else get_default_config_path()

    if not path.is_file():
        raise FileNotFoundError(f"World configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Invalid world configuration content in {path}: expected dict, got {type(config)}")

    if "global_seed" not in config or config["global_seed"] is None:
        raise ValueError(f"World configuration in {path} is missing required 'global_seed'")

    return config
