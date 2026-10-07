"""Pydantic schemas for CampaignLift API matching backend/openapi.yaml."""

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
    budget_bdt: Optional[float] = Field(default=None, gt=0.0, description="Optional budget override; defaults to campaign budget")
    exclude_negative_uplift: bool = Field(default=True, description="Whether to exclude customers with predicted uplift < 0")
    max_customers: Optional[int] = Field(default=None, ge=1, description="Optional maximum number of customers to target")
    value_per_incremental_transaction_bdt: Optional[float] = Field(
        default=None, ge=0.0, description="Assumed value per incremental transaction in BDT supplied by manager"
    )


class StrategyMetricItem(BaseModel):
    """Performance metrics for one targeting strategy."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["random", "response", "uplift", "uplift_plus_budget"] = Field(
        ...,
        description=(
            "Targeting strategy: 'random' (uniform sampling under budget), "
            "'response' (rank by response propensity p_treat under budget), "
            "'uplift' (rank strictly by predicted causal uplift under budget), "
            "'uplift_plus_budget' (causal uplift with budget optimizer: ranks by net value "
            "((uplift * assumed_value) - unit_cost) dropping negative net value when assumed value "
            "is supplied, or ranks by predicted uplift and stops when marginal predicted uplift "
            "is below zero, greedy under the same budget constraint)."
        ),
    )
    selected_count: int
    spend_bdt: float
    expected_incremental_value: float
    support: Literal["sufficient", "insufficient"]
    measured_incremental_response: Optional[float] = None
    cost_per_incremental_txn_bdt: Optional[float] = None
    negative_uplift_selected_share: float
    campaign_id: Optional[str] = Field(default=None, description="Shared campaign ID")
    eligible_population_count: Optional[int] = Field(
        default=None, description="Shared eligible population count"
    )
    budget_bdt: Optional[float] = Field(
        default=None, description="Shared budget constraint in BDT"
    )


class StrategyComparisonResponse(BaseModel):
    """Side-by-side strategy comparison across identical budget constraints."""

    model_config = ConfigDict(extra="forbid")
    campaign_id: str
    run_id: Optional[str] = None
    evaluation_split: Optional[str] = "fixture"
    eligible_population_count: Optional[int] = Field(
        default=None, description="Shared eligible population count across all strategies"
    )
    budget_bdt: Optional[float] = Field(
        default=None, description="Shared budget constraint in BDT across all strategies"
    )
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


class ExperimentSliceItem(BaseModel):
    """Performance outcome for one audience slice."""

    model_config = ConfigDict(extra="forbid")
    slice_name: str = Field(..., description="Name of the slice dimension e.g. region_code, age_band")
    slice_value: str = Field(..., description="Value of the slice dimension e.g. DHK, 25-34")
    treated_count: int = Field(..., ge=0, description="Total treated customers in this slice")
    control_count: int = Field(..., ge=0, description="Total control customers in this slice")
    support: Literal["sufficient", "insufficient"] = Field(
        ..., description="Whether randomized sample size satisfies minimum support rule (>= 30 per arm)"
    )
    treated_outcome_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Treated conversion rate, null if insufficient support"
    )
    control_outcome_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Control conversion rate, null if insufficient support"
    )
    incremental_outcome: Optional[float] = Field(
        None, description="Incremental outcome (treated - control), null if insufficient support"
    )


class ExperimentSummaryResponse(BaseModel):
    """Treatment versus control simulated trial outcomes and slices."""

    model_config = ConfigDict(extra="forbid")
    campaign_id: str
    run_id: Optional[str] = None
    total_treated: int = Field(..., ge=0, description="Total customers in treated arm")
    total_control: int = Field(..., ge=0, description="Total customers in control arm")
    treated_outcome_rate: float = Field(..., ge=0.0, le=1.0, description="Overall treated outcome rate")
    control_outcome_rate: float = Field(..., ge=0.0, le=1.0, description="Overall control outcome rate")
    overall_incremental_outcome: float = Field(
        ..., description="Overall incremental outcome rate (treated - control)"
    )
    slices: List[ExperimentSliceItem] = Field(
        default_factory=list, description="Performance broken down by slices"
    )


class FeatureContribution(BaseModel):
    """Grounded contribution of a single customer feature to predicted treatment effect."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Feature column name")
    value: str = Field(..., description="Customer's observed feature value formatted as string")
    contribution: float = Field(..., description="Attributed signed contribution value")


class CustomerExplanationResponse(BaseModel):
    """Reasoning, probabilities, reason code, and feature contributions for a single customer."""

    model_config = ConfigDict(extra="forbid")
    customer_id: str
    p_treat: float = Field(..., ge=0.0, le=1.0, description="Estimated response probability under treatment")
    p_control: float = Field(..., ge=0.0, le=1.0, description="Estimated response probability under control")
    uplift: float = Field(..., description="Estimated incremental uplift (p_treat - p_control)")
    reason_code: Literal[
        "likely_without_offer",
        "incremental_candidate",
        "weak_response",
        "negative_uplift",
    ]
    feature_contributions: List[FeatureContribution] = Field(
        default_factory=list, description="Top feature contributions ranked by magnitude"
    )
    template_text: str = Field(..., description="Grounded template explanation text")


class CopilotRequest(BaseModel):
    """Grounded campaign copilot inquiry request."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=1, max_length=1000, description="Campaign manager question")
    run_id: str = Field(..., min_length=1, description="Verified run ID providing context grounding")


class CopilotResponse(BaseModel):
    """Grounded natural-language copilot response."""

    model_config = ConfigDict(extra="forbid")
    answer: str = Field(..., description="Grounded natural language answer")
    context_fields_used: List[str] = Field(
        default_factory=list, description="List of verified run JSON fields used for answer grounding"
    )
    unavailable: bool = Field(False, description="Whether Gemini service was unavailable")

