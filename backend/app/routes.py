"""Top-level routes re-export for CampaignLift backend."""

from backend.app.api.routes import api_router, campaigns_router

__all__ = ["api_router", "campaigns_router"]
