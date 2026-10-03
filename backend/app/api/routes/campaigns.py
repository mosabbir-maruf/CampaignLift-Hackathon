"""Campaign definition and scoring API routes for CampaignLift.

Canonical planning sources:
- planning/backend_plan.md
- backend/openapi.yaml
- tasks/assaduzzaman/18_inference_api.md
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from backend.app.db import get_db
from backend.app.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    ErrorResponse,
    ScoreRunResponse,
)
from backend.app.services.inference import (
    FeatureMismatchError,
    FeatureTableNotReadyError,
    ModelNotReadyError,
    ensure_db_schema,
    score_campaign_population,
)
from backend.app.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/campaigns", tags=["Campaigns"])

# Keys that indicate an illegal customer upload attempt
CUSTOMER_UPLOAD_KEYS: Set[str] = {
    "customers",
    "customer_list",
    "customer_ids",
    "audience",
    "upload",
    "file",
    "csv",
}


def _check_no_customer_upload(data: Dict[str, Any]) -> Optional[JSONResponse]:
    """Return 400 JSONResponse if client attempts to upload customer data."""
    found = set(data.keys()).intersection(CUSTOMER_UPLOAD_KEYS)
    if found:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="customer_upload_not_allowed",
                message=(
                    "Uploading customer lists is not permitted. The system scores "
                    "pre-generated eligible populations for the active dataset version."
                ),
                detail=f"Forbidden fields provided: {sorted(list(found))}",
            ).model_dump(),
        )
    return None


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error or customer upload rejected"},
    },
    summary="Create campaign definition",
    description="Creates a new campaign scenario. Rejects uploaded customer lists.",
)
async def create_campaign(
    request: Request,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Create and persist a campaign definition."""
    try:
        raw_json = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="invalid_json",
                message="Request body must be valid JSON.",
            ).model_dump(),
        )

    # 1. Reject uploaded customer lists
    upload_err = _check_no_customer_upload(raw_json)
    if upload_err:
        return upload_err

    # 2. Validate against schema
    try:
        payload = CampaignCreateRequest(**raw_json)
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="validation_error",
                message="Invalid campaign fields.",
                detail=str(exc),
            ).model_dump(),
        )

    # 3. Persist campaign
    ensure_db_schema(conn)
    campaign_id = f"camp_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO campaigns (
            id, name, objective, offer_type, incentive_value, incentive_cost_bdt, budget_bdt, channel, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            campaign_id,
            payload.name,
            payload.objective,
            payload.offer_type,
            payload.incentive_value,
            payload.incentive_cost_bdt,
            payload.budget_bdt,
            payload.channel,
            created_at,
        ),
    )
    conn.commit()

    return CampaignResponse(
        id=campaign_id,
        name=payload.name,
        objective=payload.objective,
        offer_type=payload.offer_type,
        incentive_value=payload.incentive_value,
        incentive_cost_bdt=payload.incentive_cost_bdt,
        budget_bdt=payload.budget_bdt,
        channel=payload.channel,
        created_at=created_at,
    )


@router.get(
    "/{id}",
    response_model=CampaignResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Campaign not found"},
    },
    summary="Read campaign definition",
    description="Retrieves campaign parameters by ID.",
)
def get_campaign(
    id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Retrieve saved campaign parameters."""
    ensure_db_schema(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (id,))
    row = cursor.fetchone()

    if not row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
                detail=f"No campaign record with identifier {id}",
            ).model_dump(),
        )

    return CampaignResponse(
        id=row["id"],
        name=row["name"],
        objective=row["objective"],
        offer_type=row["offer_type"],
        incentive_value=row["incentive_value"],
        incentive_cost_bdt=row["incentive_cost_bdt"],
        budget_bdt=row["budget_bdt"],
        channel=row["channel"],
        created_at=row["created_at"],
    )


@router.post(
    "/{id}/score",
    response_model=ScoreRunResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Customer list upload rejected or invalid parameters"},
        404: {"model": ErrorResponse, "description": "Campaign not found"},
        503: {"model": ErrorResponse, "description": "Model not ready, feature missing, or feature mismatch"},
    },
    summary="Score eligible customers",
    description="Scores eligible customers for the campaign using the active model artifact.",
)
async def score_campaign(
    id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Customer score items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Execute uplift scoring for eligible customers."""
    # 1. Reject if body contains customer list
    try:
        body = await request.body()
        if body:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                upload_err = _check_no_customer_upload(parsed)
                if upload_err:
                    return upload_err
    except Exception:
        pass

    # 2. Fetch campaign
    ensure_db_schema(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (id,))
    row = cursor.fetchone()

    if not row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
                detail=f"Cannot score nonexistent campaign {id}",
            ).model_dump(),
        )

    campaign_data = dict(row)

    # 3. Score population
    try:
        result = score_campaign_population(
            campaign=campaign_data,
            limit=limit,
            offset=offset,
            settings=settings,
            conn=conn,
        )
        return result
    except ModelNotReadyError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="not_ready",
                message="Model artifact not ready to score.",
                detail=str(err),
            ).model_dump(),
        )
    except FeatureTableNotReadyError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="not_ready",
                message="Feature table not ready to score.",
                detail=str(err),
            ).model_dump(),
        )
    except FeatureMismatchError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="feature_mismatch",
                message="Feature schema mismatch. Refusing to score.",
                detail=str(err),
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="scoring_failed",
                message="Unexpected error during campaign scoring.",
                detail=str(exc),
            ).model_dump(),
        )
