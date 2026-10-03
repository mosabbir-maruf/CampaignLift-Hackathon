"""Pydantic schemas for CampaignLift API matching backend/openapi.yaml.

Canonical planning sources:
- backend/openapi.yaml
- planning/backend_plan.md
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(BaseModel):
    """Liveness probe response."""

    model_config = ConfigDict(extra="forbid")
    status: str = "ok"


class ReadyStatus(BaseModel):
    """Readiness probe response."""

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


class CampaignCreateRequest(BaseModel):
    """Campaign definition request."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=255, json_schema_extra={"example": "Q4 Merchant QR Adoption Drive"})
    objective: Literal["activation", "qr_adoption", "reactivation", "retention"]
    offer_type: Literal["flat_cashback", "pct_cashback", "fee_waiver"]
    incentive_value: float = Field(..., ge=0.0, description="BDT amount for flat, percentage for pct, 0 for fee waiver")
    incentive_cost_bdt: float = Field(..., ge=0.0, description="Expected unit incentive cost in BDT charged against budget")
    budget_bdt: float = Field(..., gt=0.0, description="Total campaign incentive budget in BDT")
    channel: Literal["push", "sms", "in_app"]


class CampaignResponse(BaseModel):
    """Campaign details response."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    objective: str
    offer_type: str
    incentive_value: float
    incentive_cost_bdt: float
    budget_bdt: float
    channel: str
    created_at: str


class CustomerScoreItem(BaseModel):
    """Individual scored customer result."""

    model_config = ConfigDict(extra="forbid")
    customer_id: str
    eligible: bool
    p_treat: float = Field(..., description="Probability of transaction if offered (response score)")
    p_control: float = Field(..., description="Probability of transaction if not offered (organic score)")
    uplift: float = Field(..., description="Incremental change in probability (p_treat - p_control)")
    response_rank: int = Field(..., ge=1, description="1-indexed rank sorted by response score p_treat descending")
    uplift_rank: int = Field(..., ge=1, description="1-indexed rank sorted by uplift descending")


class UpliftDecile(BaseModel):
    """Uplift decile summary bucket."""

    model_config = ConfigDict(extra="forbid")
    decile: int = Field(..., ge=1, le=10)
    customer_count: int = Field(..., ge=0)
    mean_uplift: float
    min_uplift: float
    max_uplift: float


class ScoreRunResponse(BaseModel):
    """Score run batch results with pagination and deciles."""

    model_config = ConfigDict(extra="forbid")
    run_id: str
    campaign_id: str
    model_version: str
    dataset_version: str
    total_eligible: int
    total_scored: int
    uplift_deciles: List[UpliftDecile] = Field(default_factory=list)
    items: List[CustomerScoreItem] = Field(default_factory=list)
    limit: int
    offset: int
    total_count: int


class OptimizeRequest(BaseModel):
    """Audience optimization and budget allocation request."""

    model_config = ConfigDict(extra="forbid")
    budget_bdt: Optional[float] = Field(None, gt=0.0, description="Optional budget override; defaults to campaign budget")
    exclude_negative_uplift: bool = Field(True, description="Whether to exclude customers with predicted uplift < 0")
    max_customers: Optional[int] = Field(None, ge=1, description="Optional maximum number of customers to target")
    value_per_incremental_transaction_bdt: Optional[float] = Field(
        None, ge=0.0, description="Assumed value per incremental transaction in BDT supplied by manager"
    )


class StrategyMetricItem(BaseModel):
    """Performance metrics for one targeting strategy."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["random", "response", "uplift"]
    selected_count: int
    spend_bdt: float
    expected_incremental_value: float
    support: Literal["sufficient", "insufficient"]
    measured_incremental_response: Optional[float] = None
    cost_per_incremental_txn_bdt: Optional[float] = None
    negative_uplift_selected_share: float


class StrategyComparisonResponse(BaseModel):
    """Side-by-side strategy comparison across identical budget constraints."""

    model_config = ConfigDict(extra="forbid")
    campaign_id: str
    run_id: Optional[str] = None
    evaluation_split: Optional[str] = "fixture"
    strategies: List[StrategyMetricItem] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    """Audience allocation and strategy comparison result."""

    model_config = ConfigDict(extra="forbid")
    strategy: str = "uplift"
    selected_count: int
    budget_bdt: float
    spend_bdt: float
    expected_incremental_value: float
    customers_excluded_negative: int
    selected_customer_ids: List[str] = Field(default_factory=list)
    comparison: StrategyComparisonResponse

