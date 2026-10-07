"""FastAPI main application for CampaignLift backend."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from backend.app.db import check_database_writable, init_db
from backend.app.settings import Settings, get_settings

# Configure structured logging to stdout
logger = logging.getLogger("campaignlift.api")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# Pydantic models matching backend/openapi.yaml components/schemas
class HealthStatus(BaseModel):
    """Liveness status response."""

    model_config = ConfigDict(extra="forbid")
    status: str = "ok"


class ReadyStatus(BaseModel):
    """Readiness status response."""

    model_config = ConfigDict(extra="forbid")
    status: str = "ready"
    model_loaded: bool
    model_version: Optional[str] = None
    dataset_version: Optional[str] = None
    feature_file_readable: bool
    database_writable: bool


class ErrorResponse(BaseModel):
    """Standard error response format."""

    model_config = ConfigDict(extra="forbid")
    error: str
    message: str
    detail: Optional[str] = None


def inspect_model_artifact(artifact_dir: Path) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Check if model artifact directory, metadata.json, and model binary exist and are valid.

    Returns:
        (model_loaded, model_version, dataset_version, error_detail)
    """
    if not artifact_dir.is_dir():
        return (
            False,
            None,
            None,
            f"Artifact directory does not exist at: {artifact_dir}",
        )

    metadata_path = artifact_dir / "metadata.json"
    if not metadata_path.is_file():
        return (
            False,
            None,
            None,
            f"Missing metadata.json at: {metadata_path}",
        )

    binary_path = artifact_dir / "model.joblib"
    if not binary_path.is_file():
        return (
            False,
            None,
            None,
            f"Missing model binary model.joblib at: {binary_path}",
        )

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        model_version = metadata.get("model_version")
        dataset_version = metadata.get("dataset_version")
        return (True, model_version, dataset_version, None)
    except Exception as exc:
        return (
            False,
            None,
            None,
            f"Failed to read metadata.json: {str(exc)}",
        )


def inspect_feature_file(feature_file_path: Path) -> tuple[bool, Optional[str]]:
    """Check if feature table path exists and is readable.

    Returns:
        (feature_file_readable, error_detail)
    """
    if not feature_file_path.is_file():
        return (
            False,
            f"Feature table file does not exist at: {feature_file_path}",
        )

    try:
        with open(feature_file_path, "rb") as f:
            # Read first chunk to verify readability
            _ = f.read(1024)
        return (True, None)
    except Exception as exc:
        return (
            False,
            f"Failed to read feature table file: {str(exc)}",
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for application startup and shutdown."""
    settings = getattr(app.state, "settings", None) or get_settings()

    # Configure logger level from settings
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    # Initialize SQLite database
    init_db(settings)

    # Inspect artifact on startup for informative logging
    model_loaded, model_v, dataset_v, _ = inspect_model_artifact(
        settings.resolved_model_artifact_dir
    )

    logger.info(
        f"CampaignLift Backend started [env={settings.app_env}] "
        f"[model_version={model_v or 'not_loaded'}] "
        f"[dataset_version={dataset_v or settings.dataset_version}] "
        f"[artifact_ready={model_loaded}]"
    )

    yield

    logger.info("CampaignLift Backend stopped.")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="CampaignLift Decision Support API",
        version="1.0.0",
        description=(
            "AI-Powered Incremental Campaign Decision Engine for MFS. "
            "Provides decision support for campaign managers to estimate incremental customer uplift, "
            "optimize marketing budget allocation, and evaluate simulated randomized experiments."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Enable CORS for local dev and frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize AuthManager in app.state
    from backend.app.auth import AuthManager, auth_router, COOKIE_NAME
    auth_mgr = AuthManager(settings)
    app.state.auth_manager = auth_mgr

    # Mount Authentication routes (/auth/login, /auth/logout, /auth/session)
    app.include_router(auth_router)

    # Role-Based Access Control Middleware for write routes (FE-04)
    @app.middleware("http")
    async def rbac_write_protection(request: Request, call_next):
        path = request.url.path
        method = request.method

        # Identify write endpoints: campaign create, score, optimize, copilot
        is_write_endpoint = (
            method in ("POST", "PUT", "PATCH", "DELETE")
            and path.startswith("/api/v1/campaigns")
        )

        if is_write_endpoint:
            # 1. Missing secret returns 503 (in production or when auth is required)
            if not auth_mgr.is_configured:
                if settings.app_env != "test" or getattr(settings, "auth_required", False):
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={
                            "error": "auth_not_configured",
                            "message": "SESSION_SECRET is missing. Write operations are unavailable.",
                        },
                    )

            # 2. When auth is configured or required, enforce Manager session
            if auth_mgr.is_configured or settings.app_env != "test" or getattr(settings, "auth_required", False):
                token = request.cookies.get(COOKIE_NAME)
                if not token:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "error": "unauthorized",
                            "message": "Authentication required. Missing session cookie.",
                        },
                    )

                session_payload = auth_mgr.verify_session_token(token)
                if not session_payload:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "error": "unauthorized",
                            "message": "Invalid or expired session cookie.",
                        },
                    )

                if session_payload.get("role") != "manager":
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "forbidden",
                            "message": "Manager role required for write actions.",
                        },
                    )

        return await call_next(request)

    # Structured request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"method={request.method} path={request.url.path} "
            f"status={response.status_code} latency_ms={duration_ms} "
            f"origin={request.headers.get('origin')} cookies={list(request.cookies.keys())}"
        )
        return response

    @app.get(
        "/health",
        response_model=HealthStatus,
        summary="Liveness check",
        description="Returns process status with no external dependency checks.",
        tags=["System"],
    )
    def get_health() -> HealthStatus:
        """Process liveness probe with zero external dependency checks."""
        return HealthStatus(status="ok")

    @app.get(
        "/ready",
        response_model=ReadyStatus,
        responses={
            503: {
                "model": ErrorResponse,
                "description": "System components not ready",
            }
        },
        summary="Readiness check",
        description="Verifies model artifact is loaded, feature table is readable, and database is writable.",
        tags=["System"],
    )
    def get_ready(
        current_settings: Settings = Depends(get_settings),
    ) -> Response:
        """Readiness check validating model artifact, feature file, and database."""
        # 1. Model artifact check
        model_loaded, model_v, dataset_v, model_err = inspect_model_artifact(
            current_settings.resolved_model_artifact_dir
        )

        # 2. Feature table check
        feature_readable, feature_err = inspect_feature_file(
            current_settings.resolved_feature_table_path
        )

        # 3. Database writability check
        db_writable = check_database_writable(current_settings)

        errors = []
        if not model_loaded:
            errors.append(f"Model artifact not ready: {model_err}")
        if not feature_readable:
            errors.append(f"Feature table not readable: {feature_err}")
        if not db_writable:
            errors.append("Database is not writable")

        if errors:
            detail = "; ".join(errors)
            logger.warning(f"Readiness check failed: {detail}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=ErrorResponse(
                    error="not_ready",
                    message="System components not ready",
                    detail=detail,
                ).model_dump(),
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=ReadyStatus(
                status="ready",
                model_loaded=True,
                model_version=model_v or "unknown",
                dataset_version=dataset_v or current_settings.dataset_version,
                feature_file_readable=True,
                database_writable=True,
            ).model_dump(),
        )

    # Mount API routes
    from backend.app.api.routes import api_router
    app.include_router(api_router)

    return app


# Default application instance for ASGI servers (e.g. uvicorn backend.app.main:app)
app = create_app()
