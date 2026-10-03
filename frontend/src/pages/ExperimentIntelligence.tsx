import { useEffect, useState } from "react"
import {
  apiClient,
  ApiError,
  type ExperimentSliceItem,
  type ExperimentSummaryResponse,
} from "../api/client"
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  SectionHeader,
  UpliftIndicator,
} from "../components/ui"
import { num, pct, pp } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"
import { navigate, useRoute } from "../lib/router"

function ArmCard({
  title,
  count,
  rate,
  kind,
}: {
  title: string
  count: number
  rate: number
  kind: "treat" | "control"
}) {
  return (
    <div className="p-5">
      <p className="flex items-center gap-2 text-[12px] text-mute uppercase tracking-wider font-medium">
        <span
          className={`size-2.5 rounded-full ${
            kind === "treat" ? "bg-primary" : "border-2 border-ink-2"
          }`}
        />
        {title}
      </p>
      <p className="tnum mt-2 font-mono text-[26px] font-semibold text-ink">
        {pct(rate)}
      </p>
      <p className="text-[12px] text-mute">Observed conversion rate</p>
      <p className="tnum mt-3 font-mono text-[12px] text-ink-2">
        {num(count)} randomized customers
      </p>
    </div>
  )
}

interface SliceRowProps {
  s: ExperimentSliceItem
  max: number
}

function SliceRow({ s, max }: SliceRowProps) {
  const isSufficient = s.support === "sufficient"
  const t = s.treated_outcome_rate
  const c = s.control_outcome_rate

  return (
    <tr className="border-b border-line/70 last:border-0 hover:bg-paper/40 transition-colors">
      <th scope="row" className="px-5 py-3 text-left font-medium text-ink">
        <span className="block text-[13px]">{s.slice_value}</span>
        <span className="font-mono text-[11px] text-mute">{s.slice_name}</span>
      </th>
      <td className="tnum px-4 py-3 text-right font-mono text-ink-2">
        {num(s.treated_count)} / {num(s.control_count)}
      </td>
      <td className="w-[32%] px-4 py-3">
        {!isSufficient || t == null || c == null ? (
          <span className="text-[12px] text-warn font-medium">
            Rates withheld (n &lt; 30 per arm)
          </span>
        ) : (
          <div
            className="space-y-1.5"
            role="img"
            aria-label={`Treatment ${pct(t)}, control ${pct(c)}`}
          >
            <div className="flex items-center gap-2">
              <div
                className="h-2 bg-primary rounded-xs transition-all duration-300"
                style={{ width: `${Math.max((t / max) * 100, 2)}%` }}
              />
              <span className="tnum font-mono text-[11px] font-medium text-ink">
                {pct(t)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="h-2 border border-ink-2 bg-surface rounded-xs transition-all duration-300"
                style={{ width: `${Math.max((c / max) * 100, 2)}%` }}
              />
              <span className="tnum font-mono text-[11px] text-mute">
                {pct(c)}
              </span>
            </div>
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono text-[13px]">
        {s.incremental_outcome != null ? (
          <UpliftIndicator value={s.incremental_outcome} />
        ) : (
          <span className="text-mute text-[12px]">Withheld</span>
        )}
      </td>
      <td className="px-5 py-3 text-right">
        <Badge tone={isSufficient ? "pos" : "warn"} dot={false}>
          {isSufficient ? "Sufficient support" : "Insufficient support"}
        </Badge>
      </td>
    </tr>
  )
}

export default function ExperimentIntelligence() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [data, setData] = useState<ExperimentSummaryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [nonce, setNonce] = useState(0)

  // Synchronize campaign ID if present in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Fetch experiment summary from backend
  useEffect(() => {
    if (!activeId) {
      setData(null)
      setLoading(false)
      setError(null)
      setNotFound(false)
      return
    }

    let alive = true
    setLoading(true)
    setError(null)
    setNotFound(false)

    apiClient
      .getExperimentSummary(activeId)
      .then((res) => {
        if (!alive) return
        setData(res)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!alive) return
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true)
          setLoading(false)
          return
        }
        let msg = "Failed to load experiment summary."
        if (err instanceof ApiError) {
          msg = err.errorResponse?.message || err.message
          if (err.errorResponse?.detail) {
            msg += ` (${err.errorResponse.detail})`
          }
        } else if (err instanceof Error) {
          msg = err.message
        }
        setError(msg)
        setLoading(false)
      })

    return () => {
      alive = false
    }
  }, [activeId, nonce])

  const slices = data?.slices ?? []
  const maxRate = Math.max(
    ...slices.flatMap((s) => [
      s.treated_outcome_rate ?? 0,
      s.control_outcome_rate ?? 0,
    ]),
    data?.treated_outcome_rate ?? 0,
    data?.control_outcome_rate ?? 0,
    0.01,
  )

  const hasInsufficientSlices = slices.some((s) => s.support === "insufficient")

  return (
    <div className="space-y-6">
      <PageHeader
        step="08"
        title="Experiment Intelligence"
        lede="Observed treatment and control outcomes from randomized trials and fixture holdouts. Displays factual backend evidence — no significance claims or fabricated intervals."
      />

      {!activeId && (
        <Panel>
          <EmptyState
            title="No campaign selected"
            action={
              <Button variant="primary" onClick={() => navigate("/setup")}>
                Go to Campaign Setup
              </Button>
            }
          >
            Select or configure a campaign first to view experiment summary
            intelligence.
          </EmptyState>
        </Panel>
      )}

      {activeId && loading && (
        <Panel>
          <LoadingState
            rows={8}
            label="Loading experiment intelligence from backend"
          />
        </Panel>
      )}

      {activeId && !loading && notFound && (
        <Panel>
          <EmptyState
            title="No experiment data found"
            action={
              <Button
                variant="primary"
                onClick={() =>
                  navigate(
                    urlCampaignId
                      ? `/budget?campaign_id=${encodeURIComponent(activeId)}`
                      : "/budget",
                  )
                }
              >
                Go to Budget Optimization
              </Button>
            }
          >
            No randomized trial or holdout test dataset is available for
            campaign &ldquo;
            {activeId}&rdquo;. Ensure holdout exposures and outcomes are
            present.
          </EmptyState>
        </Panel>
      )}

      {activeId && !loading && !notFound && error && (
        <Panel>
          <ErrorState message={error} onRetry={() => setNonce((n) => n + 1)} />
        </Panel>
      )}

      {activeId && !loading && !notFound && !error && data && (
        <>
          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
              <p className="text-[13px]">
                <span className="font-semibold text-ink">
                  Campaign Trial Evaluation:
                </span>{" "}
                <span className="font-mono text-mute">{data.campaign_id}</span>
                {data.run_id && (
                  <span className="text-mute font-mono text-[12px]">
                    {" "}
                    · {data.run_id}
                  </span>
                )}
              </p>
              <Badge tone="primary" dot={false}>
                Randomized Holdout
              </Badge>
            </div>

            <div className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
              <ArmCard
                title="Treated Arm"
                count={data.total_treated}
                rate={data.treated_outcome_rate}
                kind="treat"
              />
              <ArmCard
                title="Control Arm"
                count={data.total_control}
                rate={data.control_outcome_rate}
                kind="control"
              />
              <div className="p-5">
                <p className="text-[12px] text-mute uppercase tracking-wider font-medium">
                  Observed Incremental Effect
                </p>
                <div className="mt-2">
                  <UpliftIndicator
                    value={data.overall_incremental_outcome}
                    size="lg"
                  />
                </div>
                <p className="mt-1 text-[12px] text-mute">
                  Treatment rate minus control rate (
                  {pp(data.overall_incremental_outcome)})
                </p>
                <p className="mt-3 text-[12px] text-ink-2">
                  Observed trial difference. No hypothesis test or p-value
                  claimed.
                </p>
              </div>
            </div>

            {hasInsufficientSlices && (
              <div className="border-t border-line bg-warn-soft/50 px-5 py-3 text-[12.5px] text-ink-2">
                <span className="font-semibold text-warn">Support notice:</span>{" "}
                Some demographic slices have fewer than 30 observations per arm.
                Conversion rates for those slices are withheld by the backend to
                prevent spurious inference.
              </div>
            )}
          </Panel>

          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-5">
              <SectionHeader
                title="Audience Slice Breakdown"
                meta="Factual trial segment performance"
              />
              <div className="mb-3 flex gap-3 text-[11.5px] text-mute">
                <span className="flex items-center gap-1.5">
                  <span className="size-2.5 bg-primary rounded-xs" />
                  Treatment arm
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="size-2.5 border border-ink-2 rounded-xs" />
                  Control arm
                </span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-[13px]">
                <caption className="sr-only">
                  Trial results by demographic slice
                </caption>
                <thead>
                  <tr className="border-y border-line text-[11.5px] font-medium text-mute">
                    <th scope="col" className="px-5 py-2.5 text-left">
                      Slice
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Sample (treat / control)
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-left">
                      Conversion Rates
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Incremental Effect
                    </th>
                    <th scope="col" className="px-5 py-2.5 text-right">
                      Support Level
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {slices.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-5 py-6 text-center text-mute text-[13px]"
                      >
                        No audience slice dimensions reported by backend.
                      </td>
                    </tr>
                  ) : (
                    slices.map((s) => (
                      <SliceRow
                        key={`${s.slice_name}_${s.slice_value}`}
                        s={s}
                        max={maxRate}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <p className="border-t border-line px-5 py-3 text-[12px] text-mute">
              Slice outcomes reflect factual test logs. Small subgroups carry
              wide variance; only slices with sufficient sample support (&ge; 30
              per arm) display computed rates.
            </p>
          </Panel>
        </>
      )}
    </div>
  )
}
