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
    CopilotRequest,
    CopilotResponse,
    CustomerExplanationResponse,
    ErrorResponse,
    ExperimentSummaryResponse,
    OptimizeRequest,
    OptimizeResponse,
    ScoreRunResponse,
    StrategyComparisonResponse,
)
from backend.app.services.inference import (
    FeatureMismatchError,
    FeatureTableNotReadyError,
    ModelNotReadyError,
    ensure_db_schema,
    score_campaign_population,
)
from backend.app.services.experiment import (
    ExperimentDataNotReadyError,
    ensure_experiment_db_schema,
    get_or_create_experiment_summary,
)
from backend.app.services.explain import (
    CustomerNotFoundError,
    ensure_explain_db_schema,
    explain_customer,
)
from backend.app.services.gemini import (
    CopilotDisabledError,
    CopilotUnavailableError,
    RunNotFoundError,
    query_copilot,
)
from backend.app.services.optimizer import (
    ensure_optimizer_db_schema,
    optimize_campaign_budget,
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


@router.post(
    "/{id}/optimize",
    response_model=OptimizeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid budget or optimization parameters"},
        404: {"model": ErrorResponse, "description": "Campaign not found"},
        503: {"model": ErrorResponse, "description": "Scored population or model not ready"},
    },
    summary="Allocate campaign budget",
    description="Greedy knapsack audience selection under budget constraints maximizing incremental value.",
)
async def optimize_budget(
    id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Execute greedy knapsack budget allocation for campaign."""
    ensure_db_schema(conn)
    ensure_optimizer_db_schema(conn)

    # 1. Fetch campaign
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (id,))
    camp_row = cursor.fetchone()

    if not camp_row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
                detail=f"Cannot optimize nonexistent campaign {id}",
            ).model_dump(),
        )

    campaign_data = dict(camp_row)

    # Parse and validate request body if provided
    try:
        body = await request.body()
        if body:
            raw_json = json.loads(body)
            payload = OptimizeRequest(**raw_json)
        else:
            payload = OptimizeRequest()
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="invalid_budget",
                message="Invalid budget or optimization parameters.",
                detail=str(exc),
            ).model_dump(),
        )

    # 2. Fetch scored customers or score on-the-fly
    cursor.execute("SELECT * FROM customer_scores WHERE campaign_id = ?", (id,))
    scored_rows = [dict(r) for r in cursor.fetchall()]

    if not scored_rows:
        try:
            score_campaign_population(
                campaign=campaign_data,
                limit=200,
                offset=0,
                settings=settings,
                conn=conn,
            )
            cursor.execute("SELECT * FROM customer_scores WHERE campaign_id = ?", (id,))
            scored_rows = [dict(r) for r in cursor.fetchall()]
        except ModelNotReadyError as err:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=ErrorResponse(
                    error="not_ready",
                    message="Model artifact not ready for scoring.",
                    detail=str(err),
                ).model_dump(),
            )
        except FeatureTableNotReadyError as err:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=ErrorResponse(
                    error="not_ready",
                    message="Feature table not ready for scoring.",
                    detail=str(err),
                ).model_dump(),
            )
        except FeatureMismatchError as err:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=ErrorResponse(
                    error="feature_mismatch",
                    message="Feature schema mismatch. Refusing to optimize.",
                    detail=str(err),
                ).model_dump(),
            )

    # 3. Optimize budget
    try:
        opt_response = optimize_campaign_budget(
            campaign=campaign_data,
            scored_customers=scored_rows,
            request=payload,
            conn=conn,
        )
        return opt_response
    except ValueError as val_err:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="invalid_budget",
                message=str(val_err),
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="optimization_failed",
                message="Unexpected error during budget optimization.",
                detail=str(exc),
            ).model_dump(),
        )


@router.get(
    "/{id}/comparison",
    response_model=StrategyComparisonResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Campaign or comparison not found"},
    },
    summary="Compare targeting strategies",
    description="Retrieves side-by-side strategy comparison for Random, Response, and Uplift targeting.",
)
def get_strategy_comparison(
    id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Retrieve saved strategy comparison for campaign."""
    ensure_db_schema(conn)
    ensure_optimizer_db_schema(conn)

    cursor = conn.cursor()
    # Check campaign exists
    cursor.execute("SELECT id FROM campaigns WHERE id = ?", (id,))
    if not cursor.fetchone():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
            ).model_dump(),
        )

    # Check comparison
    cursor.execute(
        "SELECT comparison_json FROM strategy_comparisons WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
        (id,),
    )
    row = cursor.fetchone()

    if not row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="comparison_not_found",
                message=f"No strategy comparison available for campaign '{id}'. Run optimization first.",
            ).model_dump(),
        )

    return json.loads(row["comparison_json"])


@router.get(
    "/{id}/experiment",
    response_model=ExperimentSummaryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Campaign or experiment run not found"},
        503: {"model": ErrorResponse, "description": "Experiment data not ready"},
    },
    summary="Treatment vs control experiment summary",
    description="Summarizes randomized trial outcomes and slice-level performance from simulated treatment versus control arms.",
)
def get_experiment_summary(
    id: str,
    split: Optional[str] = Query(None, description="Optional split filter: 'test', 'fixture', 'all'"),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Retrieve treatment vs control experiment summary and slice metrics."""
    ensure_db_schema(conn)
    ensure_experiment_db_schema(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (id,))
    camp_row = cursor.fetchone()

    if not camp_row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
                detail=f"Cannot retrieve experiment summary for nonexistent campaign {id}",
            ).model_dump(),
        )

    try:
        summary = get_or_create_experiment_summary(
            campaign_id=id,
            split=split,
            settings=settings,
            conn=conn,
        )
        return summary
    except ExperimentDataNotReadyError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="not_ready",
                message="Experiment data not ready.",
                detail=str(err),
            ).model_dump(),
        )
    except ValueError as val_err:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="invalid_experiment_data",
                message=str(val_err),
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="experiment_summary_failed",
                message="Unexpected error computing experiment summary.",
                detail=str(exc),
            ).model_dump(),
        )


@router.get(
    "/{id}/customers/{customer_id}/explanation",
    response_model=CustomerExplanationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Campaign or customer not found"},
        503: {"model": ErrorResponse, "description": "Model or feature data not ready"},
    },
    summary="Get customer-level explanation",
    description="Provides grounded reasoning, feature contributions, probabilities, and reason code for an individual customer recommendation.",
)
def get_customer_explanation(
    id: str,
    customer_id: str,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Retrieve grounded reasoning and feature contributions for one customer."""
    ensure_db_schema(conn)
    ensure_explain_db_schema(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (id,))
    camp_row = cursor.fetchone()

    if not camp_row:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
                detail=f"Cannot retrieve explanation for nonexistent campaign {id}",
            ).model_dump(),
        )

    campaign_data = dict(camp_row)

    try:
        explanation = explain_customer(
            campaign=campaign_data,
            customer_id=customer_id,
            settings=settings,
            conn=conn,
        )
        return explanation
    except CustomerNotFoundError as err:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="customer_not_found",
                message=f"Customer '{customer_id}' not found in campaign population.",
                detail=str(err),
            ).model_dump(),
        )
    except ModelNotReadyError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="not_ready",
                message="Model artifact not ready for explanation.",
                detail=str(err),
            ).model_dump(),
        )
    except FeatureTableNotReadyError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="not_ready",
                message="Feature table not ready for explanation.",
                detail=str(err),
            ).model_dump(),
        )
    except FeatureMismatchError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="feature_mismatch",
                message="Feature schema mismatch. Refusing to explain.",
                detail=str(err),
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="explanation_failed",
                message="Unexpected error computing customer explanation.",
                detail=str(exc),
            ).model_dump(),
        )


@router.post(
    "/{id}/copilot",
    response_model=CopilotResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid question or missing run_id"},
        404: {"model": ErrorResponse, "description": "Campaign or run not found"},
        503: {"model": ErrorResponse, "description": "Copilot disabled or unavailable"},
    },
    summary="Grounded campaign copilot",
    description="Answers campaign manager questions strictly using verified run JSON context. Rejects prompt injection and does not invent metrics or causal claims.",
)
def ask_copilot(
    id: str,
    payload: CopilotRequest,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    """Answer question strictly using verified run JSON context."""
    ensure_db_schema(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT id FROM campaigns WHERE id = ?", (id,))
    if not cursor.fetchone():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="campaign_not_found",
                message=f"Campaign '{id}' not found.",
            ).model_dump(),
        )

    try:
        response = query_copilot(
            campaign_id=id,
            request=payload,
            conn=conn,
            settings=settings,
        )
        return response
    except RunNotFoundError as err:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error="run_not_found",
                message=f"Run '{payload.run_id}' not found for campaign '{id}'.",
                detail=str(err),
            ).model_dump(),
        )
    except CopilotDisabledError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="copilot_disabled",
                message="Copilot is disabled. GEMINI_API_KEY is not configured.",
                detail=str(err),
            ).model_dump(),
        )
    except CopilotUnavailableError as err:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error="copilot_unavailable",
                message="Gemini Copilot service is currently unavailable.",
                detail=str(err),
            ).model_dump(),
        )
    except ValueError as val_err:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error="invalid_copilot_request",
                message=str(val_err),
            ).model_dump(),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="copilot_failed",
                message="Unexpected error executing Copilot inquiry.",
                detail=str(exc),
            ).model_dump(),
        )



