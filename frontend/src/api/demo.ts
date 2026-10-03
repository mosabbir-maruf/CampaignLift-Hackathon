// ILLUSTRATIVE FIXTURES ONLY.
// These values exist so the interface can be reviewed before backend integration.
// They are not CampaignLift results and must never be presented as such.

import type {
  AudienceSummary,
  Campaign,
  CopilotResponse,
  CustomerExplanation,
  ExperimentSummary,
  OptimizationResult,
  ScoredCustomer,
  StrategyResult,
  TargetingStatus,
  UpliftDecile,
} from "./types"

export const DEMO_CAMPAIGN: Campaign = {
  campaign_id: "CMP-2041",
  name: "Q4 Cash-Out Reactivation",
  objective: "Reactivate dormant cash-out users",
  offer_type: "Cashback",
  offer_value: 50,
  start_date: "2026-10-15",
  end_date: "2026-11-15",
  budget: 500000,
  eligibility_context:
    "No cash-out in last 60 days, active wallet, KYC verified",
  targeting_strategy: "uplift",
  status: "scored",
  created_at: "2026-10-01T09:20:00Z",
}

const REASONS: Record<TargetingStatus, { code: string; segment: string }[]> = {
  high_incremental: [
    { code: "R01_HIGH_SENSITIVITY", segment: "Offer-sensitive, low baseline" },
    { code: "R02_DIGITAL_ENGAGED", segment: "Digitally engaged, lapsed" },
  ],
  low_incremental: [
    { code: "R05_LOW_EFFECT", segment: "Indifferent to offer" },
  ],
  likely_without_offer: [
    { code: "R03_HIGH_BASELINE", segment: "Habitual transactor" },
  ],
  negative_uplift: [
    { code: "R04_OFFER_FATIGUE", segment: "Recent offer fatigue" },
  ],
  insufficient_support: [
    { code: "R09_SPARSE_HISTORY", segment: "New / sparse history" },
  ],
}

function rng(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildCustomers(): ScoredCustomer[] {
  const r = rng(42)
  const fixed: ScoredCustomer[] = [
    {
      customer_id: "CUS-10482",
      p_treat: 0.72,
      p_control: 0.18,
      uplift: 0.54,
      targeting_status: "high_incremental",
      reason_code: "R01_HIGH_SENSITIVITY",
      segment: "Offer-sensitive, low baseline",
    },
    {
      customer_id: "CUS-20915",
      p_treat: 0.93,
      p_control: 0.91,
      uplift: 0.02,
      targeting_status: "likely_without_offer",
      reason_code: "R03_HIGH_BASELINE",
      segment: "Habitual transactor",
    },
    {
      customer_id: "CUS-31077",
      p_treat: 0.21,
      p_control: 0.4,
      uplift: -0.19,
      targeting_status: "negative_uplift",
      reason_code: "R04_OFFER_FATIGUE",
      segment: "Recent offer fatigue",
    },
  ]
  const weights: [TargetingStatus, number][] = [
    ["high_incremental", 0.24],
    ["likely_without_offer", 0.22],
    ["low_incremental", 0.34],
    ["negative_uplift", 0.1],
    ["insufficient_support", 0.1],
  ]
  const rows: ScoredCustomer[] = [...fixed]
  for (let i = 0; i < 237; i++) {
    let x = r()
    let status: TargetingStatus = "low_incremental"
    for (const [s, w] of weights) {
      if (x < w) {
        status = s
        break
      }
      x -= w
    }
    let pc: number, pt: number
    if (status === "high_incremental") {
      pc = 0.05 + r() * 0.3
      pt = pc + 0.15 + r() * 0.4
    } else if (status === "likely_without_offer") {
      pc = 0.7 + r() * 0.25
      pt = Math.min(0.99, pc + r() * 0.05)
    } else if (status === "negative_uplift") {
      pc = 0.25 + r() * 0.4
      pt = pc - 0.04 - r() * 0.2
    } else if (status === "insufficient_support") {
      pc = 0.2 + r() * 0.4
      pt = pc + (r() - 0.4) * 0.2
    } else {
      pc = 0.1 + r() * 0.5
      pt = pc + (r() - 0.3) * 0.08
    }
    const reason = REASONS[status][Math.floor(r() * REASONS[status].length)]
    rows.push({
      customer_id: `CUS-${String(10000 + Math.floor(r() * 89999)).padStart(5, "0")}`,
      p_treat: +pt.toFixed(3),
      p_control: +pc.toFixed(3),
      uplift: +(pt - pc).toFixed(3),
      targeting_status: status,
      reason_code: reason.code,
      segment: reason.segment,
    })
  }
  return rows
}

export const DEMO_CUSTOMERS: ScoredCustomer[] = buildCustomers()

export const DEMO_AUDIENCE_SUMMARY: AudienceSummary = {
  eligible_customers: 184320,
  scored_at: "2026-10-02T14:05:00Z",
  by_status: {
    high_incremental: 41210,
    likely_without_offer: 39870,
    low_incremental: 64450,
    negative_uplift: 19630,
    insufficient_support: 19160,
  },
}

export const DEMO_DECILES: UpliftDecile[] = [
  {
    decile: 1,
    customers: 18432,
    mean_p_treat: 0.61,
    mean_p_control: 0.2,
    mean_uplift: 0.41,
  },
  {
    decile: 2,
    customers: 18432,
    mean_p_treat: 0.55,
    mean_p_control: 0.24,
    mean_uplift: 0.31,
  },
  {
    decile: 3,
    customers: 18432,
    mean_p_treat: 0.49,
    mean_p_control: 0.27,
    mean_uplift: 0.22,
  },
  {
    decile: 4,
    customers: 18432,
    mean_p_treat: 0.46,
    mean_p_control: 0.31,
    mean_uplift: 0.15,
  },
  {
    decile: 5,
    customers: 18432,
    mean_p_treat: 0.44,
    mean_p_control: 0.35,
    mean_uplift: 0.09,
  },
  {
    decile: 6,
    customers: 18432,
    mean_p_treat: 0.47,
    mean_p_control: 0.43,
    mean_uplift: 0.04,
  },
  {
    decile: 7,
    customers: 18432,
    mean_p_treat: 0.58,
    mean_p_control: 0.57,
    mean_uplift: 0.01,
  },
  {
    decile: 8,
    customers: 18432,
    mean_p_treat: 0.71,
    mean_p_control: 0.72,
    mean_uplift: -0.01,
  },
  {
    decile: 9,
    customers: 18432,
    mean_p_treat: 0.36,
    mean_p_control: 0.42,
    mean_uplift: -0.06,
  },
  {
    decile: 10,
    customers: 18432,
    mean_p_treat: 0.24,
    mean_p_control: 0.37,
    mean_uplift: -0.13,
  },
]

export const DEMO_STRATEGIES: StrategyResult[] = [
  {
    strategy: "random",
    label: "Random targeting",
    ranks_by: "No ranking — uniform sample of eligible customers",
    expected: {
      target_population: 10000,
      expected_conversions: 4410,
      expected_incremental_conversions: 790,
      expected_incremental_value: 158000,
      spend: 500000,
      incremental_per_1k_spend: 1.58,
    },
    measured: null,
  },
  {
    strategy: "response",
    label: "Response-based",
    ranks_by: "Highest p_treat — likelihood to respond when offered",
    expected: {
      target_population: 10000,
      expected_conversions: 8120,
      expected_incremental_conversions: 610,
      expected_incremental_value: 122000,
      spend: 500000,
      incremental_per_1k_spend: 1.22,
    },
    measured: null,
  },
  {
    strategy: "uplift",
    label: "Uplift targeting",
    ranks_by: "Highest uplift — p_treat minus p_control",
    expected: {
      target_population: 10000,
      expected_conversions: 5940,
      expected_incremental_conversions: 3860,
      expected_incremental_value: 772000,
      spend: 500000,
      incremental_per_1k_spend: 7.72,
    },
    measured: null,
  },
]

export const DEMO_OPTIMIZATION: OptimizationResult = {
  status: "optimal",
  budget: 500000,
  available_budget: 500000,
  cost_per_offer: 50,
  eligible_customers: 184320,
  prioritized_customers: 41210,
  selected_customers: 10000,
  expected_spend: 500000,
  expected_incremental_conversions: 3860,
  expected_incremental_value: 772000,
  excluded_negative: 19630,
  constraints: [
    { label: "Total spend ≤ budget", value: "৳500,000", binding: true },
    { label: "Exclude negative uplift", value: "Enabled", binding: false },
    { label: "Minimum uplift threshold", value: "+5.0 pp", binding: false },
    { label: "Exclude insufficient support", value: "Enabled", binding: false },
  ],
}

export const DEMO_EXPLANATIONS: Record<string, CustomerExplanation> = {
  "CUS-10482": {
    customer_id: "CUS-10482",
    decision: "prioritize",
    p_treat: 0.72,
    p_control: 0.18,
    uplift: 0.54,
    targeting_status: "high_incremental",
    reason_code: "R01_HIGH_SENSITIVITY",
    reason_text:
      "High campaign sensitivity with low natural transaction propensity.",
    contributions: [
      {
        feature: "past_offer_redemption",
        label: "Past offer redemption",
        value: "3 of 4 offers",
        contribution: 0.17,
      },
      {
        feature: "days_since_cashout",
        label: "Days since last cash-out",
        value: "74 days",
        contribution: 0.12,
      },
      {
        feature: "app_sessions_30d",
        label: "App sessions (30d)",
        value: "11",
        contribution: 0.09,
      },
      {
        feature: "agent_proximity",
        label: "Agent proximity",
        value: "0.4 km",
        contribution: 0.05,
      },
      {
        feature: "avg_txn_value",
        label: "Avg. transaction value",
        value: "৳1,240",
        contribution: -0.03,
      },
    ],
  },
  "CUS-20915": {
    customer_id: "CUS-20915",
    decision: "do_not_prioritize",
    p_treat: 0.93,
    p_control: 0.91,
    uplift: 0.02,
    targeting_status: "likely_without_offer",
    reason_code: "R03_HIGH_BASELINE",
    reason_text:
      "Likely to transact without an offer; low expected incremental effect.",
    contributions: [
      {
        feature: "txn_frequency_30d",
        label: "Transactions (30d)",
        value: "22",
        contribution: -0.08,
      },
      {
        feature: "days_since_cashout",
        label: "Days since last cash-out",
        value: "61 days",
        contribution: 0.04,
      },
      {
        feature: "past_offer_redemption",
        label: "Past offer redemption",
        value: "1 of 5 offers",
        contribution: -0.03,
      },
      {
        feature: "app_sessions_30d",
        label: "App sessions (30d)",
        value: "34",
        contribution: 0.02,
      },
    ],
  },
  "CUS-31077": {
    customer_id: "CUS-31077",
    decision: "do_not_prioritize",
    p_treat: 0.21,
    p_control: 0.4,
    uplift: -0.19,
    targeting_status: "negative_uplift",
    reason_code: "R04_OFFER_FATIGUE",
    reason_text:
      "Offer fatigue — signals associated with lower response when contacted.",
    contributions: [
      {
        feature: "offers_received_90d",
        label: "Offers received (90d)",
        value: "7",
        contribution: -0.14,
      },
      {
        feature: "notification_optout",
        label: "Push opt-out history",
        value: "Yes",
        contribution: -0.06,
      },
      {
        feature: "days_since_cashout",
        label: "Days since last cash-out",
        value: "63 days",
        contribution: 0.03,
      },
      {
        feature: "complaint_flag",
        label: "Recent complaint",
        value: "1 (30d)",
        contribution: -0.02,
      },
    ],
  },
}

export const DEMO_EXPERIMENT: ExperimentSummary = {
  experiment_id: "EXP-0917",
  period: "2026-08-01 → 2026-08-31",
  treatment: { population: 24000, conversions: 6240, response_rate: 0.26 },
  control: { population: 6000, conversions: 1200, response_rate: 0.2 },
  incremental_effect: 0.06,
  support: "limited",
  support_note:
    "Backend reports limited support for segment-level estimates. No significance test was supplied.",
  segments: [
    {
      segment: "High uplift",
      treatment: { population: 6100, conversions: 2440, response_rate: 0.4 },
      control: { population: 1520, conversions: 334, response_rate: 0.22 },
      incremental_effect: 0.18,
      support: "sufficient",
    },
    {
      segment: "Medium uplift",
      treatment: { population: 7200, conversions: 1940, response_rate: 0.27 },
      control: { population: 1800, conversions: 396, response_rate: 0.22 },
      incremental_effect: 0.05,
      support: "sufficient",
    },
    {
      segment: "Low uplift",
      treatment: { population: 8400, conversions: 1600, response_rate: 0.19 },
      control: { population: 2100, conversions: 399, response_rate: 0.19 },
      incremental_effect: 0.0,
      support: "limited",
    },
    {
      segment: "Negative uplift",
      treatment: { population: 2300, conversions: 260, response_rate: null },
      control: { population: 580, conversions: 71, response_rate: null },
      incremental_effect: null,
      support: "insufficient",
    },
  ],
}

export const DEMO_COPILOT_SUGGESTIONS = [
  "Why is CUS-10482 prioritized?",
  "Which customers should we avoid targeting?",
  "How does uplift targeting differ from response targeting?",
  "What does the current budget allocation imply?",
  "Which segments show the strongest incremental response?",
]

export const DEMO_COPILOT_ANSWERS: Record<string, CopilotResponse> = {
  "Why is CUS-10482 prioritized?": {
    answer:
      "CUS-10482 has an estimated p_treat of 72.0% and p_control of 18.0%, an uplift of +54.0 pp. The reason code is R01_HIGH_SENSITIVITY. The largest model contributions are past offer redemption (3 of 4) and 74 days since last cash-out. These are signals associated with the prediction, not proven causes.",
    context_fields_used: [
      "customer.p_treat",
      "customer.p_control",
      "customer.uplift",
      "customer.reason_code",
      "explanation.contributions",
    ],
  },
  "Which customers should we avoid targeting?": {
    answer:
      'The scored audience has 19,630 customers with status "Potential negative uplift". The current optimization excludes them. Another 19,160 have insufficient support and are also excluded until more evidence is available.',
    context_fields_used: [
      "audience.by_status.negative_uplift",
      "audience.by_status.insufficient_support",
      "optimization.constraints",
    ],
  },
  "How does uplift targeting differ from response targeting?": {
    answer:
      "Response targeting ranks by p_treat — who is likely to respond when offered. Many of those customers would respond anyway. Uplift targeting ranks by p_treat − p_control. For this campaign the backend estimates 3,860 incremental conversions for uplift targeting against 610 for response targeting at the same spend. Both are expected values; no measured holdout result is available yet.",
    context_fields_used: [
      "strategies[].expected.expected_incremental_conversions",
      "strategies[].measured",
      "strategies[].ranks_by",
    ],
  },
}

export const DEMO_COPILOT_FALLBACK: CopilotResponse = {
  answer:
    "In preview mode there is no grounded answer for this question. Once connected, the backend Copilot will answer using the campaign, scoring, optimization and experiment context listed below.",
  context_fields_used: ["campaign", "audience", "optimization"],
}
