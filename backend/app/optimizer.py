"""Top-level optimizer module re-export for CampaignLift backend."""

from backend.app.services.optimizer import (
    ensure_optimizer_db_schema,
    evaluate_test_slice,
    load_test_exposures_and_outcomes,
    optimize_campaign_budget,
)

__all__ = [
    "ensure_optimizer_db_schema",
    "load_test_exposures_and_outcomes",
    "evaluate_test_slice",
    "optimize_campaign_budget",
]
