import { useEffect, useState } from "react"
import {
  apiClient,
  type CampaignResponse,
  type ReadyStatus,
  type CampaignObjective,
  type CampaignOfferType,
} from "../api/client"
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricBlock,
  PageHeader,
  Panel,
  SectionHeader,
} from "../components/ui"
import { Link, useRoute } from "../lib/router"
import { bdt } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"

const OBJECTIVE_LABELS: Record<CampaignObjective, string> = {
  reactivation: "Dormant Reactivation",
  activation: "User Activation",
  qr_adoption: "Merchant QR Adoption",
  retention: "Churn Retention",
}

const OFFER_LABELS: Record<CampaignOfferType, string> = {
  flat_cashback: "Flat Cashback",
  pct_cashback: "Percentage Cashback",
  fee_waiver: "Fee Waiver",
}

const NEXT_STEPS = [
  {
    to: "/setup",
    n: "02",
    t: "Campaign Setup",
    d: "Create or modify campaign scenarios and incentive budgets.",
  },
  {
    to: "/audience",
    n: "03",
    t: "Audience Scoring",
    d: "Run model inference on the eligible population to score customer uplift.",
  },
  {
    to: "/strategy",
    n: "05",
    t: "Strategy Comparison",
    d: "Compare uplift targeting against response-based ranking.",
  },
  {
    to: "/budget",
    n: "06",
    t: "Budget Optimization",
    d: "Allocate incentive spend to maximize incremental impact.",
  },
]

export default function Overview() {
  const { query } = useRoute()
  const [campaign, setCampaign] = useState<CampaignResponse | null>(null)
  const [ready, setReady] = useState<ReadyStatus | null>(null)
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">(
    "loading",
  )
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // Determine active campaign ID from query parameter or stored active campaign
  const urlCampaignId = query.get("campaign_id") || query.get("id")
  const activeId = urlCampaignId || getActiveCampaignId()

  useEffect(() => {
    let alive = true
    setStatus("loading")
    setError(null)

    // Synchronize URL campaign ID to active storage if provided
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }

    if (!activeId) {
      // No campaign selected: fetch readiness probe to verify backend state
      apiClient
        .getReady()
        .then((r) => {
          if (!alive) return
          setReady(r)
          setStatus("empty")
        })
        .catch(() => {
          if (!alive) return
          setStatus("empty")
        })
      return () => {
        alive = false
      }
    }

    // Fetch active campaign definition and system readiness in parallel
    Promise.all([
      apiClient.getCampaign(activeId),
      apiClient.getReady().catch(() => null),
    ])
      .then(([campRes, readyRes]) => {
        if (!alive) return
        setCampaign(campRes)
        setReady(readyRes)
        setStatus("ready")
      })
      .catch((err: unknown) => {
        if (!alive) return
        const msg =
          err instanceof Error
            ? err.message
            : `Failed to load campaign "${activeId}".`
        setError(msg)
        setStatus("error")
      })

    return () => {
      alive = false
    }
  }, [activeId, urlCampaignId, nonce])

  return (
    <div className="space-y-6">
      <PageHeader
        step="01"
        title="Overview"
        lede="Active campaign parameters and system verification. Model inference and uplift predictions are computed during Audience Scoring."
        actions={
          status === "ready" && campaign ? (
            <div className="flex items-center gap-2">
              <Badge tone="neu" dot={false}>
                <span className="font-mono text-[11px]">{campaign.id}</span>
              </Badge>
              <Badge tone="pos">{campaign.channel.toUpperCase()}</Badge>
            </div>
          ) : status === "empty" ? (
            <Badge tone="warn">No Active Campaign</Badge>
          ) : null
        }
      />

      {/* Loading State */}
      {status === "loading" && (
        <Panel className="p-6">
          <LoadingState
            rows={7}
            label="Retrieving campaign definition and model status from API"
          />
        </Panel>
      )}

      {/* Error State */}
      {status === "error" && (
        <Panel className="p-6">
          <ErrorState message={error} onRetry={() => setNonce((n) => n + 1)} />
          <div className="mt-4 border-t border-line pt-4">
            <Link
              to="/setup"
              className="inline-flex items-center gap-2 text-[13px] font-medium text-primary hover:underline"
            >
              Go to Campaign Setup to create a new campaign →
            </Link>
          </div>
        </Panel>
      )}

      {/* Empty State: No Campaign Configured */}
      {status === "empty" && (
        <div className="space-y-6">
          <Panel className="p-6">
            <EmptyState
              title="No Campaign Configured"
              action={
                <Link
                  to="/setup"
                  className="inline-flex items-center gap-2 rounded-[4px] bg-primary px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-primary-hover"
                >
                  Create Campaign Scenario →
                </Link>
              }
            >
              No active campaign definition is selected. Create a campaign
              scenario in Campaign Setup to configure the incentive budget,
              channel, and targeting objective before running audience scoring.
            </EmptyState>
          </Panel>

          {/* System Readiness block if available */}
          {ready && (
            <Panel className="p-5">
              <SectionHeader title="System & Inference Engine Readiness" />
              <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4 text-[13px]">
                <div className="border border-line/70 bg-paper p-3 rounded-[3px]">
                  <p className="text-mute text-[11px] uppercase tracking-wider font-mono">
                    Model Status
                  </p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <Badge tone={ready.model_loaded ? "pos" : "warn"}>
                      {ready.model_loaded ? "Model Ready" : "Model Not Loaded"}
                    </Badge>
                  </div>
                </div>
                <div className="border border-line/70 bg-paper p-3 rounded-[3px]">
                  <p className="text-mute text-[11px] uppercase tracking-wider font-mono">
                    Model Version
                  </p>
                  <p className="mt-1 font-mono font-medium text-ink">
                    {ready.model_version || "Not reported"}
                  </p>
                </div>
                <div className="border border-line/70 bg-paper p-3 rounded-[3px]">
                  <p className="text-mute text-[11px] uppercase tracking-wider font-mono">
                    Dataset Version
                  </p>
                  <p className="mt-1 font-mono font-medium text-ink">
                    {ready.dataset_version || "Not reported"}
                  </p>
                </div>
                <div className="border border-line/70 bg-paper p-3 rounded-[3px]">
                  <p className="text-mute text-[11px] uppercase tracking-wider font-mono">
                    Database Connection
                  </p>
                  <p className="mt-1 font-medium text-ink">
                    {ready.database_writable ? "Writable" : "Read-only"}
                  </p>
                </div>
              </div>
            </Panel>
          )}
        </div>
      )}

      {/* Ready State: Live Campaign Loaded from API */}
      {status === "ready" && campaign && (
        <div className="space-y-6">
          <Panel>
            <div className="grid lg:grid-cols-[1.2fr_1fr]">
              {/* Column 1: Active Campaign Specification */}
              <div className="border-b border-line p-5 lg:border-r lg:border-b-0 lg:p-6">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-mono text-[11px] tracking-wider text-mute uppercase">
                    Active Scenario
                  </p>
                  <Badge tone="pos">Configured</Badge>
                </div>
                <h2 className="mt-2 text-[20px] font-semibold tracking-tight text-ink">
                  {campaign.name}
                </h2>
                <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">
                  Objective:{" "}
                  <span className="font-medium text-ink">
                    {OBJECTIVE_LABELS[campaign.objective] || campaign.objective}
                  </span>
                  . Incentive allocation is capped at{" "}
                  <span className="font-mono font-semibold text-ink">
                    {bdt(campaign.budget_bdt)}
                  </span>{" "}
                  delivered via{" "}
                  <span className="font-medium uppercase text-ink">
                    {campaign.channel}
                  </span>
                  .
                </p>

                {/* Pipeline Metrics: Honest uncalculated states */}
                <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line pt-5 sm:grid-cols-4">
                  <MetricBlock
                    label="Configured Budget"
                    value={bdt(campaign.budget_bdt)}
                    note="Scenario budget cap"
                  />
                  <MetricBlock
                    label="Unit Incentive Cost"
                    value={bdt(campaign.incentive_cost_bdt)}
                    note="Per-customer cost"
                  />
                  <MetricBlock
                    label="Scored Audience"
                    value="—"
                    note="Pending Step 03 scoring"
                  />
                  <MetricBlock
                    label="Expected Incr. Conv."
                    value="—"
                    note="Awaiting score run"
                  />
                </dl>

                {/* Scoring Status Notice */}
                <div className="mt-6 rounded-[4px] border border-line bg-paper p-4">
                  <p className="text-[12.5px] font-medium text-ink">
                    Audience Scoring Pending
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                    This campaign scenario is saved in the database. Individual
                    customer uplift predictions, decile ranking, and budget
                    optimization require executing the inference model.
                  </p>
                  <div className="mt-3">
                    <Link
                      to={`/audience?campaign_id=${campaign.id}`}
                      className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-primary underline-offset-2 hover:underline"
                    >
                      Proceed to Step 03: Audience Scoring →
                    </Link>
                  </div>
                </div>
              </div>

              {/* Column 2: Parameters & Backend Model Verification */}
              <div className="p-5 lg:p-6 space-y-5">
                <SectionHeader title="Scenario Parameters" />
                <dl className="divide-y divide-line text-[13px]">
                  <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                    <dt className="text-mute">Campaign ID</dt>
                    <dd className="font-mono text-ink text-[12px]">
                      {campaign.id}
                    </dd>
                  </div>
                  <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                    <dt className="text-mute">Offer Type</dt>
                    <dd className="text-ink">
                      {OFFER_LABELS[campaign.offer_type] || campaign.offer_type}
                    </dd>
                  </div>
                  <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                    <dt className="text-mute">Incentive Value</dt>
                    <dd className="font-mono text-ink text-[12px]">
                      {campaign.offer_type === "pct_cashback"
                        ? `${campaign.incentive_value}%`
                        : campaign.offer_type === "fee_waiver"
                          ? "Fee waiver (0)"
                          : bdt(campaign.incentive_value)}
                    </dd>
                  </div>
                  <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                    <dt className="text-mute">Channel</dt>
                    <dd className="text-ink uppercase">{campaign.channel}</dd>
                  </div>
                  <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                    <dt className="text-mute">Created At</dt>
                    <dd className="font-mono text-[12px] text-ink">
                      {new Date(campaign.created_at).toUTCString().slice(5, 22)}{" "}
                      UTC
                    </dd>
                  </div>
                </dl>

                <div className="border-t border-line pt-4">
                  <SectionHeader title="Model & Runtime Status" />
                  <dl className="divide-y divide-line text-[13px]">
                    <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                      <dt className="text-mute">Model Status</dt>
                      <dd>
                        <Badge tone={ready?.model_loaded ? "pos" : "warn"}>
                          {ready?.model_loaded
                            ? "Model Loaded"
                            : "Model Offline / Not Loaded"}
                        </Badge>
                      </dd>
                    </div>
                    <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                      <dt className="text-mute">Model Version</dt>
                      <dd className="font-mono text-[12px] text-ink">
                        {ready?.model_version || "Not reported"}
                      </dd>
                    </div>
                    <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                      <dt className="text-mute">Dataset Version</dt>
                      <dd className="font-mono text-[12px] text-ink">
                        {ready?.dataset_version || "Not reported"}
                      </dd>
                    </div>
                    <div className="grid grid-cols-[130px_1fr] gap-3 py-2">
                      <dt className="text-mute">Feature Store</dt>
                      <dd className="text-ink">
                        {ready?.feature_file_readable
                          ? "Available"
                          : "Not Readable"}
                      </dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>

            {/* Pipeline Stage Status Section */}
            <div className="border-t border-line p-5 lg:p-6 bg-paper/50">
              <SectionHeader title="Decision Pipeline Status" />
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-[4px] border border-line bg-surface p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-mute uppercase">
                      Stage 01
                    </span>
                    <Badge tone="pos">Complete</Badge>
                  </div>
                  <p className="mt-2 text-[14px] font-medium text-ink">
                    Campaign Setup
                  </p>
                  <p className="mt-1 text-[12px] text-mute">
                    Scenario definitions and financial bounds persisted in
                    database.
                  </p>
                </div>

                <div className="rounded-[4px] border border-line bg-surface p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-mute uppercase">
                      Stage 02
                    </span>
                    <Badge tone="warn">Pending</Badge>
                  </div>
                  <p className="mt-2 text-[14px] font-medium text-ink">
                    Audience Scoring
                  </p>
                  <p className="mt-1 text-[12px] text-mute">
                    Inference on eligible population to compute p_treat,
                    p_control, and uplift.
                  </p>
                  <Link
                    to={`/audience?campaign_id=${campaign.id}`}
                    className="mt-2.5 inline-block text-[12px] font-medium text-primary hover:underline"
                  >
                    Open Audience →
                  </Link>
                </div>

                <div className="rounded-[4px] border border-line bg-surface p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-mute uppercase">
                      Stage 03
                    </span>
                    <Badge tone="neu">Pending</Badge>
                  </div>
                  <p className="mt-2 text-[14px] font-medium text-ink">
                    Budget Optimization
                  </p>
                  <p className="mt-1 text-[12px] text-mute">
                    Knapsack allocation prioritizing high-incremental users
                    under spend limits.
                  </p>
                  <Link
                    to={`/budget?campaign_id=${campaign.id}`}
                    className="mt-2.5 inline-block text-[12px] font-medium text-primary hover:underline"
                  >
                    Open Budget →
                  </Link>
                </div>
              </div>
            </div>
          </Panel>
        </div>
      )}

      {/* Inspect Next Section */}
      <section aria-labelledby="next-heading">
        <h2
          id="next-heading"
          className="mb-3 text-[13px] font-semibold tracking-wide uppercase text-mute"
        >
          Workflow Navigation
        </h2>
        <ol className="grid gap-px overflow-hidden rounded-[5px] border border-line bg-line md:grid-cols-4">
          {NEXT_STEPS.map((s) => {
            const dest = campaign ? `${s.to}?campaign_id=${campaign.id}` : s.to
            return (
              <li key={s.to} className="bg-surface">
                <Link
                  to={dest}
                  className="group block h-full p-4 hover:bg-paper"
                >
                  <span className="font-mono text-[11px] text-mute">{s.n}</span>
                  <p className="mt-1 text-[14px] font-medium text-ink group-hover:text-primary">
                    {s.t} <span aria-hidden>→</span>
                  </p>
                  <p className="mt-1 text-[12px] text-mute leading-relaxed">
                    {s.d}
                  </p>
                </Link>
              </li>
            )
          })}
        </ol>
      </section>
    </div>
  )
}
