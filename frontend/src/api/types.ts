// Types mirroring the CampaignLift backend contract.
// Field names follow backend concepts; adjust to the final schema during integration.
// The frontend never computes these values — it only renders them.

export type TargetingStatus = "high_incremental" | "low_incremental" | "likely_without_offer" | "negative_uplift" | "insufficient_support"

export type StrategyKey = "random" | "response" | "uplift" | "uplift_plus_budget"

export interface CampaignConfig {
  name: string
  objective: string
  offer_type: string
  offer_value: number
  start_date: string
  end_date: string
  budget: number
  eligibility_context: string
  targeting_strategy: StrategyKey
}

export interface Campaign extends CampaignConfig {
  campaign_id: string
  status: "draft" | "scored" | "optimized" | "live" | "closed"
  created_at: string
}

export interface ScoredCustomer {
  customer_id: string
  p_treat: number
  p_control: number
  uplift: number
  targeting_status: TargetingStatus
  reason_code: string
  segment: string
}

export interface UpliftDecile {
  decile: number
  customers?: number
  customer_count?: number
  mean_p_treat?: number
  mean_p_control?: number
  mean_uplift: number
  min_uplift?: number
  max_uplift?: number
}

export interface AudienceSummary {
  eligible_customers: number
  scored_at: string
  by_status: Record<TargetingStatus, number>
}

export interface StrategyMetrics {
  target_population: number
  expected_conversions: number
  expected_incremental_conversions: number
  expected_incremental_value: number
  spend: number
  incremental_per_1k_spend: number
}

export interface StrategyResult {
  strategy: StrategyKey
  label: string
  ranks_by: string
  expected: StrategyMetrics
  /** Null when no holdout test has been measured. Never fabricated. */
  measured: Partial<StrategyMetrics> | null
}

export interface BudgetConstraint {
  label: string
  value: string
  binding: boolean
}

export interface OptimizationResult {
  status: "optimal" | "budget_unused" | "insufficient_support" | "infeasible"
  budget: number
  available_budget: number
  cost_per_offer: number
  eligible_customers: number
  prioritized_customers: number
  selected_customers: number
  expected_spend: number
  expected_incremental_conversions: number
  expected_incremental_value: number
  excluded_negative: number
  constraints: BudgetConstraint[]
  message?: string
}

export interface FeatureContribution {
  feature: string
  label: string
  value: string
  contribution: number
}

export interface CustomerExplanation {
  customer_id: string
  decision: "prioritize" | "do_not_prioritize" | "review"
  p_treat: number
  p_control: number
  uplift: number
  targeting_status: TargetingStatus
  reason_code: string
  reason_text: string
  contributions: FeatureContribution[]
}

export interface ExperimentArm {
  population: number
  conversions: number
  response_rate: number | null
}

export interface ExperimentSegment {
  segment: string
  treatment: ExperimentArm
  control: ExperimentArm
  incremental_effect: number | null
  support: "sufficient" | "limited" | "insufficient"
}

export interface ExperimentSummary {
  experiment_id: string
  period: string
  treatment: ExperimentArm
  control: ExperimentArm
  incremental_effect: number | null
  support: "sufficient" | "limited" | "insufficient"
  support_note?: string
  segments: ExperimentSegment[]
}

export interface CopilotResponse {
  answer: string
  context_fields_used: string[]
}

export type UserRole = "manager" | "viewer"

export interface UserSession {
  authenticated: boolean
  role: UserRole
  username: string
}
