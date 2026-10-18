/**
 * CampaignLift Typed API Client
 *
 * Derived strictly from backend/openapi.yaml.
 * Presentation layer only — all scoring, uplift modeling, and optimization
 * calculations are performed by the FastAPI backend service.
 * Never store API keys, credentials, or tokens in this file.
 */

// --- OpenAPI Schema Types ---

export interface HealthStatus {
  status: string
}

export interface ReadyStatus {
  status: string
  model_loaded: boolean
  model_version?: string
  dataset_version?: string
  feature_file_readable: boolean
  database_writable: boolean
}

export interface ErrorResponse {
  error: string
  message: string
  detail?: string
}

export type CampaignObjective = "activation" | "qr_adoption" | "reactivation" | "retention"

export type CampaignOfferType = "flat_cashback" | "pct_cashback" | "fee_waiver"

export type CampaignChannel = "push" | "sms" | "in_app"

export type CampaignStatus = "draft" | "configured" | "scored" | "optimized" | "active" | "completed"

export interface CampaignCreateRequest {
  name: string
  objective: CampaignObjective
  offer_type: CampaignOfferType
  incentive_value: number
  incentive_cost_bdt: number
  budget_bdt: number
  channel: CampaignChannel
}

export interface CampaignResponse {
  id: string
  name: string
  objective: CampaignObjective
  offer_type: CampaignOfferType
  incentive_value: number
  incentive_cost_bdt: number
  budget_bdt: number
  channel: CampaignChannel
  created_at: string
}

export interface CustomerScoreItem {
  customer_id: string
  eligible: boolean
  p_treat: number
  p_control: number
  uplift: number
  response_rank: number
  uplift_rank: number
}

export interface UpliftDecileItem {
  decile: number
  customer_count: number
  mean_uplift: number
  min_uplift: number
  max_uplift: number
}

export interface ScoreRunResponse {
  run_id: string
  campaign_id: string
  model_version: string
  dataset_version: string
  total_eligible: number
  total_scored: number
  uplift_deciles?: UpliftDecileItem[]
  items: CustomerScoreItem[]
  limit: number
  offset: number
  total_count: number
}

export interface OptimizeRequest {
  budget_bdt?: number
  exclude_negative_uplift?: boolean
  max_customers?: number
  value_per_incremental_transaction_bdt?: number
}

export type StrategyName = "random" | "response" | "uplift"
export type StrategySupport = "sufficient" | "insufficient"

export interface StrategyMetricItem {
  strategy: StrategyName
  selected_count: number
  spend_bdt: number
  expected_incremental_value: number
  support: StrategySupport
  measured_incremental_response?: number | null
  cost_per_incremental_txn_bdt?: number | null
  negative_uplift_selected_share: number
}

export interface StrategyComparisonResponse {
  campaign_id: string
  run_id?: string
  evaluation_split?: string
  strategies: StrategyMetricItem[]
}

export interface OptimizeResponse {
  strategy: string
  selected_count: number
  budget_bdt: number
  spend_bdt: number
  expected_incremental_value: number
  customers_excluded_negative: number
  selected_customer_ids?: string[]
  comparison: StrategyComparisonResponse
}

export interface FeatureContributionItem {
  name: string
  value: string
  contribution: number
}

export type ExplanationReasonCode = "likely_without_offer" | "incremental_candidate" | "weak_response" | "negative_uplift"

export interface CustomerExplanationResponse {
  customer_id: string
  p_treat: number
  p_control: number
  uplift: number
  reason_code: ExplanationReasonCode
  feature_contributions: FeatureContributionItem[]
  template_text: string
}

export interface ExperimentSliceItem {
  slice_name: string
  slice_value: string
  treated_count: number
  control_count: number
  support: StrategySupport
  treated_outcome_rate?: number | null
  control_outcome_rate?: number | null
  incremental_outcome?: number | null
}

export interface ExperimentSummaryResponse {
  campaign_id: string
  run_id?: string
  total_treated: number
  total_control: number
  treated_outcome_rate: number
  control_outcome_rate: number
  overall_incremental_outcome: number
  slices: ExperimentSliceItem[]
}

export interface CopilotRequest {
  question: string
  run_id: string
}

export interface CopilotResponse {
  answer: string
  context_fields_used: string[]
  unavailable: boolean
}

// --- Client Configuration & Infrastructure ---

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/+$/,
    "",
  ) || ""

export const hasBackend = Boolean(BASE_URL)

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly errorResponse?: ErrorResponse,
    message?: string,
  ) {
    super(
      message ||
        errorResponse?.message ||
        `API request failed with status ${status}`,
    )
    this.name = "ApiError"
  }
}

export function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  let base = BASE_URL
  if (typeof window !== "undefined" && base) {
    try {
      const parsed = new URL(base, window.location.origin)
      if (
        (window.location.hostname === "127.0.0.1" &&
          parsed.hostname === "localhost") ||
        (window.location.hostname === "localhost" &&
          parsed.hostname === "127.0.0.1")
      ) {
        parsed.hostname = window.location.hostname
        base = parsed.origin
      }
    } catch {
      // ignore
    }
  }
  if (!base) {
    return normalizedPath
  }
  // If base already ends with /api and path starts with /api/, avoid /api/api/
  if (base.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${base.slice(0, -4)}${normalizedPath}`
  }
  // If base is /api and path is top-level endpoint like /ready or /health
  if (
    base === "/api" &&
    (normalizedPath === "/ready" || normalizedPath === "/health")
  ) {
    return normalizedPath
  }
  return `${base}${normalizedPath}`
}

export async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!BASE_URL) {
    throw new Error("VITE_API_BASE_URL is not configured")
  }
  const url = buildUrl(path)

  const res = await fetch(url, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  })

  if (!res.ok) {
    let errBody: ErrorResponse | undefined
    try {
      errBody = ((await res.json()) as ErrorResponse)
    } catch {
      // response was not JSON
    }
    throw new ApiError(res.status, errBody, errBody?.message)
  }

  return (await res.json()) as T
}

// --- Typed Endpoints Matching backend/openapi.yaml ---

export async function getHealth(): Promise<HealthStatus> {
  return fetchJson<HealthStatus>("/health")
}

export async function getReady(): Promise<ReadyStatus> {
  return fetchJson<ReadyStatus>("/ready")
}

export async function createCampaign(
  req: CampaignCreateRequest,
): Promise<CampaignResponse> {
  return fetchJson<CampaignResponse>("/api/v1/campaigns", {
    method: "POST",
    body: JSON.stringify(req),
  })
}

export async function getCampaign(id: string): Promise<CampaignResponse> {
  return fetchJson<CampaignResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}`,
  )
}

export interface ScoreCampaignOptions {
  limit?: number
  offset?: number
}

export async function scoreCampaign(
  id: string,
  options?: ScoreCampaignOptions,
): Promise<ScoreRunResponse> {
  const params = new URLSearchParams()
  if (options?.limit !== undefined) params.set("limit", String(options.limit))
  if (options?.offset !== undefined)
    params.set("offset", String(options.offset))
  const qs = params.toString() ? `?${params.toString()}` : ""
  return fetchJson<ScoreRunResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/score${qs}`,
    { method: "POST" },
  )
}

export async function optimizeBudget(
  id: string,
  req?: OptimizeRequest,
): Promise<OptimizeResponse> {
  return fetchJson<OptimizeResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/optimize`,
    {
      method: "POST",
      body: req ? JSON.stringify(req) : undefined,
    },
  )
}

export async function getStrategyComparison(
  id: string,
): Promise<StrategyComparisonResponse> {
  return fetchJson<StrategyComparisonResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/comparison`,
  )
}

export async function getCustomerExplanation(
  id: string,
  customerId: string,
): Promise<CustomerExplanationResponse> {
  return fetchJson<CustomerExplanationResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/customers/${encodeURIComponent(customerId)}/explanation`,
  )
}

export async function getExperimentSummary(
  id: string,
): Promise<ExperimentSummaryResponse> {
  return fetchJson<ExperimentSummaryResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/experiment`,
  )
}

export async function queryCopilot(
  id: string,
  req: CopilotRequest,
): Promise<CopilotResponse> {
  return fetchJson<CopilotResponse>(
    `/api/v1/campaigns/${encodeURIComponent(id)}/copilot`,
    {
      method: "POST",
      body: JSON.stringify(req),
    },
  )
}

export interface LoginResponse {
  status: string
  role: "manager" | "viewer"
  username: string
}

export interface LogoutResponse {
  status: string
  message: string
}

export interface SessionResponse {
  status: string
  authenticated: boolean
  role?: "manager" | "viewer"
  username?: string
}

export async function login(
  username: "manager" | "viewer",
  password: string,
): Promise<LoginResponse> {
  return fetchJson<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  })
}

export async function logout(): Promise<LogoutResponse> {
  return fetchJson<LogoutResponse>("/auth/logout", {
    method: "POST",
  })
}

export async function getSession(): Promise<SessionResponse> {
  return fetchJson<SessionResponse>("/auth/session")
}

export const apiClient = {
  getHealth,
  getReady,
  login,
  logout,
  getSession,
  createCampaign,
  getCampaign,
  scoreCampaign,
  optimizeBudget,
  getStrategyComparison,
  getCustomerExplanation,
  getExperimentSummary,
  queryCopilot,
}
