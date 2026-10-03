import { useEffect, useState } from "react"
import { apiClient, ApiError, type ScoreRunResponse } from "../api/client"
import DecileChart from "../components/DecileChart"
import {
  Badge,
  Button,
  DumbbellLegend,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  SectionHeader,
  UpliftIndicator,
} from "../components/ui"
import { Link, navigate, useRoute } from "../lib/router"
import { pct, pp } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"

export default function UpliftAnalysis() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id") || query.get("id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [data, setData] = useState<ScoreRunResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // Synchronize campaign ID if provided in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Fetch scoring run and deciles for active campaign
  useEffect(() => {
    if (!activeId) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }

    let alive = true
    setLoading(true)
    setError(null)

    apiClient
      .scoreCampaign(activeId, { limit: 50, offset: 0 })
      .then((res) => {
        if (!alive) return
        setData(res)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!alive) return
        let msg = "Failed to load uplift analysis."
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

  const deciles = data?.uplift_deciles ?? []
  const topProfiles = (data?.items ?? []).slice(0, 5)

  return (
    <div className="space-y-6">
      <PageHeader
        step="04"
        title="Uplift Analysis"
        lede="Uplift estimates the expected incremental response from treatment compared with no treatment: p_treat − p_control, evaluated by backend causal inference."
        actions={
          data ? (
            <div className="flex items-center gap-2">
              <Badge tone="neu" dot={false}>
                <span className="font-mono text-[11px]">
                  {data.campaign_id}
                </span>
              </Badge>
              <Button
                onClick={() =>
                  navigate(
                    activeId
                      ? `/strategy?campaign_id=${encodeURIComponent(activeId)}`
                      : "/strategy",
                  )
                }
              >
                Strategy comparison →
              </Button>
            </div>
          ) : null
        }
      />

      {/* Empty State: No Campaign Selected */}
      {!activeId && (
        <Panel className="p-6">
          <EmptyState
            title="No Campaign Selected"
            action={
              <Link
                to="/setup"
                className="inline-flex items-center gap-2 rounded-[4px] bg-primary px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-primary-hover"
              >
                Go to Campaign Setup →
              </Link>
            }
          >
            No active campaign scenario was selected. Define a campaign scenario
            in Campaign Setup before analyzing uplift deciles.
          </EmptyState>
        </Panel>
      )}

      {/* Error State: Scoring / Decile fetch error */}
      {activeId && error && (
        <Panel className="p-6">
          <ErrorState message={error} onRetry={() => setNonce((n) => n + 1)} />
          <div className="mt-4 flex items-center gap-3 border-t border-line pt-4 text-[12.5px]">
            <Link
              to={
                activeId
                  ? `/audience?campaign_id=${encodeURIComponent(activeId)}`
                  : "/audience"
              }
              className="font-medium text-primary hover:underline"
            >
              ← Go to Audience Scoring
            </Link>
            <span className="text-mute">·</span>
            <Link to="/" className="font-medium text-primary hover:underline">
              Open Overview
            </Link>
          </div>
        </Panel>
      )}

      {/* Loading State: Inference running */}
      {activeId && loading && (
        <Panel className="p-6">
          <LoadingState
            rows={8}
            label="Loading uplift decile distribution from backend inference engine"
          />
        </Panel>
      )}

      {/* Ready State */}
      {activeId && !loading && !error && data && (
        <>
          {/* Section 1: Representative Customer Scored Profiles */}
          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
              <div>
                <h2 className="text-[13px] font-semibold tracking-wide uppercase text-ink">
                  Top Scored Customer Profiles
                </h2>
                <p className="mt-0.5 text-[12px] text-mute">
                  Top customer predictions ranked by incremental uplift from
                  backend model inference.
                </p>
              </div>
              <DumbbellLegend />
            </div>

            {topProfiles.length === 0 ? (
              <div className="p-6">
                <EmptyState title="No customer profiles returned">
                  No individual customer score items were returned in the
                  scoring response.
                </EmptyState>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[13px]">
                  <caption className="sr-only">
                    Treatment, control and uplift for top scored customers
                  </caption>
                  <thead>
                    <tr className="border-b border-line text-[11.5px] font-medium text-mute">
                      <th scope="col" className="px-5 py-2 text-left">
                        Customer
                      </th>
                      <th scope="col" className="px-3 py-2 text-right">
                        Treatment
                      </th>
                      <th scope="col" className="px-3 py-2 text-right">
                        Control
                      </th>
                      <th scope="col" className="w-[32%] px-3 py-2 text-left">
                        Response probability (0–100%)
                      </th>
                      <th scope="col" className="px-5 py-2 text-right">
                        Uplift
                      </th>
                      <th scope="col" className="px-3 py-2 text-right">
                        Uplift Rank
                      </th>
                      <th scope="col" className="px-3 py-2 text-right">
                        Response Rank
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {topProfiles.map((c) => (
                      <tr
                        key={c.customer_id}
                        className="border-b border-line/70 last:border-0 hover:bg-paper"
                      >
                        <td className="px-5 py-3 align-middle">
                          <Link
                            to={`/explain?id=${encodeURIComponent(c.customer_id)}&campaign_id=${encodeURIComponent(data.campaign_id)}`}
                            className="font-mono text-[13px] font-medium text-ink hover:text-primary hover:underline"
                          >
                            {c.customer_id}
                          </Link>
                          <div className="mt-1">
                            <Badge tone={c.eligible ? "pos" : "neu"}>
                              {c.eligible ? "Eligible" : "Ineligible"}
                            </Badge>
                          </div>
                        </td>
                        <td className="tnum px-3 py-3 text-right align-middle font-mono text-[14px]">
                          {pct(c.p_treat)}
                        </td>
                        <td className="tnum px-3 py-3 text-right align-middle font-mono text-[14px] text-ink-2">
                          {pct(c.p_control)}
                        </td>
                        <td className="px-3 py-3 align-middle">
                          <ProbabilityDumbbell
                            pTreat={c.p_treat}
                            pControl={c.p_control}
                            height="lg"
                            axis
                          />
                        </td>
                        <td className="px-5 py-3 text-right align-middle">
                          <UpliftIndicator value={c.uplift} size="lg" />
                        </td>
                        <td className="tnum px-3 py-3 text-right align-middle font-mono text-[12px] font-medium text-ink">
                          #{c.uplift_rank}
                        </td>
                        <td className="tnum px-3 py-3 text-right align-middle font-mono text-[12px] text-mute">
                          #{c.response_rank}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="border-t border-line bg-paper px-5 py-3 text-[12.5px] text-ink-2">
              A high baseline responder is not the optimal target if they would
              transact regardless of incentive. Uplift targeting prioritizes
              customers with the widest positive gap between treatment and
              control.
            </p>
          </Panel>

          {/* Section 2: Uplift Deciles Chart & Detail Table */}
          {deciles.length === 0 ? (
            <Panel className="p-6">
              <EmptyState title="Uplift Deciles Unavailable">
                The scoring response did not contain uplift decile buckets for
                this campaign. Run scoring in Audience to generate deciles.
              </EmptyState>
            </Panel>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
              {/* Diverging Bar Chart Panel */}
              <Panel className="p-5">
                <SectionHeader
                  title="Uplift distribution by decile"
                  meta={`uplift_deciles · ${data.model_version}`}
                />
                <DecileChart deciles={deciles} />
              </Panel>

              {/* Decile Detail Table Panel */}
              <Panel>
                <div className="px-5 pt-5">
                  <SectionHeader title="Decile detail" />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12.5px]">
                    <caption className="sr-only">Backend decile values</caption>
                    <thead>
                      <tr className="border-b border-line text-[11px] font-medium text-mute">
                        <th scope="col" className="px-5 py-2 text-left">
                          Decile
                        </th>
                        <th scope="col" className="px-2 py-2 text-right">
                          Customers
                        </th>
                        <th scope="col" className="px-3 py-2 text-right">
                          Mean Uplift
                        </th>
                        <th scope="col" className="px-5 py-2 text-right">
                          Range [Min → Max]
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {deciles.map((d) => (
                        <tr
                          key={d.decile}
                          className="border-b border-line/60 last:border-0 hover:bg-paper"
                        >
                          <td className="tnum px-5 py-2 font-mono font-medium text-ink">
                            D{d.decile}
                          </td>
                          <td className="tnum px-2 py-2 text-right font-mono text-ink-2">
                            {d.customer_count.toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <UpliftIndicator value={d.mean_uplift} />
                          </td>
                          <td className="tnum px-5 py-2 text-right font-mono text-[11px] text-mute">
                            {pp(d.min_uplift)} → {pp(d.max_uplift)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </div>
          )}

          {/* Workflow Footer Navigation */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[4px] border border-line bg-surface p-4 text-[13px]">
            <div className="text-mute">
              Campaign:{" "}
              <span className="font-mono text-ink">{data.campaign_id}</span> ·
              Run: <span className="font-mono text-ink">{data.run_id}</span>
            </div>
            <div className="flex items-center gap-3">
              <Link
                to={`/audience?campaign_id=${encodeURIComponent(data.campaign_id)}`}
                className="font-medium text-primary hover:underline"
              >
                ← Inspect All Scored Customers
              </Link>
              <span className="text-mute">·</span>
              <Link
                to={`/strategy?campaign_id=${encodeURIComponent(data.campaign_id)}`}
                className="font-medium text-primary hover:underline"
              >
                Compare Targeting Strategies →
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
