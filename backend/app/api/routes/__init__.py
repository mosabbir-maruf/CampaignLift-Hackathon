"""API routes package for CampaignLift backend."""

from fastapi import APIRouter

from backend.app.api.routes.campaigns import router as campaigns_router

api_router = APIRouter()
api_router.include_router(campaigns_router)

__all__ = ["api_router", "campaigns_router"]
