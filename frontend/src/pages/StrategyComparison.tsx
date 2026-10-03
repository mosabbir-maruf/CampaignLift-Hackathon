import { useEffect, useState } from "react"
import {
  apiClient,
  ApiError,
  type StrategyMetricItem,
  type StrategyComparisonResponse,
  type StrategyName,
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
} from "../components/ui"
import { bdt, num, pct, pp } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"
import { navigate, useRoute } from "../lib/router"

interface StrategyConfig {
  label: string
  ranks_by: string
}

const STRATEGY_CONFIG: Record<StrategyName, StrategyConfig> = {
  uplift: {
    label: "Uplift targeting",
    ranks_by: "Ranked by predicted uplift (CATE)",
  },
  response: {
    label: "Response-based",
    ranks_by: "Ranked by predicted response (p_treat)",
  },
  random: {
    label: "Random allocation",
    ranks_by: "Un-targeted baseline",
  },
}

function StrategyBars({ strategies }: { strategies: StrategyMetricItem[] }) {
  const maxVal = Math.max(
    ...strategies.map((s) => Math.max(0, s.expected_incremental_value)),
    0.01,
  )

  return (
    <div className="space-y-4">
      {strategies.map((s) => {
        const config = STRATEGY_CONFIG[s.strategy] || {
          label: s.strategy,
          ranks_by: "",
        }
        const val = Math.max(0, s.expected_incremental_value)
        const pctWidth = Math.max((val / maxVal) * 100, 2)
        const isUplift = s.strategy === "uplift"

        return (
          <div key={s.strategy}>
            <div className="mb-1 flex justify-between text-[12.5px]">
              <span
                className={isUplift ? "font-semibold text-ink" : "text-ink-2"}
              >
                {config.label}
              </span>
              <span className="tnum font-mono text-mute">
                <span className={isUplift ? "font-semibold text-pos" : ""}>
                  {val.toFixed(2)}
                </span>{" "}
                exp. incremental value
              </span>
            </div>
            <div
              className="flex h-5 w-full bg-sunken rounded-xs overflow-hidden"
              role="img"
              aria-label={`${config.label}: ${val.toFixed(2)} expected incremental value`}
            >
              <div
                className={`h-full transition-all duration-300 ${
                  isUplift
                    ? "bg-pos"
                    : s.strategy === "response"
                      ? "bg-primary/50"
                      : "bg-neu/40"
                }`}
                style={{ width: `${pctWidth}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[11px] text-mute font-mono">
              <span>{num(s.selected_count)} targeted</span>
              <span>{bdt(s.spend_bdt)} spend</span>
            </div>
          </div>
        )
      })}
      <div className="flex flex-wrap gap-4 pt-2 text-[11.5px] text-mute border-t border-line/50">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 bg-pos rounded-xs" />
          Uplift targeting (causal optimization)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 bg-primary/50 rounded-xs" />
          Response baseline
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 bg-neu/40 rounded-xs" />
          Random allocation
        </span>
      </div>
    </div>
  )
}

export default function StrategyComparison() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id") || query.get("id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [data, setData] = useState<StrategyComparisonResponse | null>(null)
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

  // Fetch strategy comparison from backend
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
      .getStrategyComparison(activeId)
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
        let msg = "Failed to load strategy comparison."
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

  return (
    <div className="space-y-6">
      <PageHeader
        step="05"
        title="Strategy Comparison"
        lede="Response prediction asks who will convert. Uplift prediction asks who will convert because of the offer. At equal spend, these choose different customers."
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
            Select or configure a campaign first to view strategy comparisons.
          </EmptyState>
        </Panel>
      )}

      {activeId && loading && (
        <Panel>
          <LoadingState rows={8} label="Loading strategy comparison from API" />
        </Panel>
      )}

      {activeId && !loading && notFound && (
        <Panel>
          <EmptyState
            title="Optimization not yet run"
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
            No strategy comparison is available for campaign &ldquo;{activeId}
            &rdquo;. Run budget optimization first to calculate and persist
            side-by-side strategy evaluations.
          </EmptyState>
        </Panel>
      )}

      {activeId && !loading && !notFound && error && (
        <Panel>
          <ErrorState message={error} onRetry={() => setNonce((n) => n + 1)} />
        </Panel>
      )}

      {activeId &&
        !loading &&
        !notFound &&
        !error &&
        data &&
        (() => {
          const strategies = data.strategies ?? []
          const hasMeasured = strategies.some(
            (s) =>
              s.measured_incremental_response != null ||
              s.cost_per_incremental_txn_bdt != null,
          )

          return (
            <>
              <Panel>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-[13px]">
                    <caption className="sr-only">Strategy comparison</caption>
                    <thead>
                      <tr className="border-b border-line-strong">
                        <th
                          scope="col"
                          className="w-[26%] px-5 py-3 text-left align-bottom text-[11.5px] font-medium text-mute"
                        >
                          Metric
                        </th>
                        {strategies.map((s) => {
                          const cfg = STRATEGY_CONFIG[s.strategy] || {
                            label: s.strategy,
                            ranks_by: "",
                          }
                          const isUplift = s.strategy === "uplift"

                          return (
                            <th
                              key={s.strategy}
                              scope="col"
                              className={`px-5 py-3 text-right align-bottom ${
                                isUplift ? "bg-primary-soft/60" : ""
                              }`}
                            >
                              <div className="flex flex-col items-end gap-1">
                                <span className="flex items-center justify-end gap-2 text-[13.5px] font-semibold text-ink">
                                  {isUplift && (
                                    <Badge tone="primary" dot={false}>
                                      Selected
                                    </Badge>
                                  )}
                                  {cfg.label}
                                </span>
                                <span className="text-[11.5px] font-normal text-mute">
                                  {cfg.ranks_by}
                                </span>
                                <span className="mt-1">
                                  {s.support === "insufficient" ? (
                                    <Badge tone="warn" dot={false}>
                                      Insufficient support
                                    </Badge>
                                  ) : (
                                    <Badge tone="pos" dot={false}>
                                      Sufficient support
                                    </Badge>
                                  )}
                                </span>
                              </div>
                            </th>
                          )
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th
                          colSpan={strategies.length + 1}
                          scope="colgroup"
                          className="bg-paper px-5 py-1.5 text-left font-mono text-[10.5px] font-medium tracking-wider text-mute uppercase"
                        >
                          Expected · model estimates
                        </th>
                      </tr>
                      <tr className="border-b border-line/70">
                        <th
                          scope="row"
                          className="px-5 py-2.5 text-left font-normal text-ink-2"
                        >
                          Target population
                        </th>
                        {strategies.map((s) => (
                          <td
                            key={s.strategy}
                            className={`tnum px-5 py-2.5 text-right font-mono ${
                              s.strategy === "uplift"
                                ? "bg-primary-soft/60"
                                : ""
                            }`}
                          >
                            {num(s.selected_count)}
                          </td>
                        ))}
                      </tr>
                      <tr className="border-b border-line/70">
                        <th
                          scope="row"
                          className="px-5 py-2.5 text-left font-normal text-ink-2"
                        >
                          Spend
                        </th>
                        {strategies.map((s) => (
                          <td
                            key={s.strategy}
                            className={`tnum px-5 py-2.5 text-right font-mono ${
                              s.strategy === "uplift"
                                ? "bg-primary-soft/60"
                                : ""
                            }`}
                          >
                            {bdt(s.spend_bdt)}
                          </td>
                        ))}
                      </tr>
                      <tr className="border-b border-line/70">
                        <th
                          scope="row"
                          className="px-5 py-2.5 text-left font-medium text-ink"
                        >
                          Expected incremental value
                        </th>
                        {strategies.map((s) => (
                          <td
                            key={s.strategy}
                            className={`tnum px-5 py-2.5 text-right font-mono ${
                              s.strategy === "uplift"
                                ? "bg-primary-soft/60 font-semibold text-pos"
                                : ""
                            }`}
                          >
                            {s.expected_incremental_value.toFixed(2)}
                          </td>
                        ))}
                      </tr>
                      <tr className="border-b border-line/70">
                        <th
                          scope="row"
                          className="px-5 py-2.5 text-left font-normal text-ink-2"
                        >
                          Negative uplift share
                        </th>
                        {strategies.map((s) => (
                          <td
                            key={s.strategy}
                            className={`tnum px-5 py-2.5 text-right font-mono ${
                              s.strategy === "uplift"
                                ? "bg-primary-soft/60"
                                : ""
                            }`}
                          >
                            {pct(s.negative_uplift_selected_share)}
                          </td>
                        ))}
                      </tr>

                      <tr>
                        <th
                          colSpan={strategies.length + 1}
                          scope="colgroup"
                          className="bg-paper px-5 py-1.5 text-left font-mono text-[10.5px] font-medium tracking-wider text-mute uppercase"
                        >
                          Measured on test · holdout
                        </th>
                      </tr>
                      {hasMeasured ? (
                        <>
                          <tr className="border-b border-line/70">
                            <th
                              scope="row"
                              className="px-5 py-2.5 text-left font-normal text-ink-2"
                            >
                              Measured incremental response
                            </th>
                            {strategies.map((s) => (
                              <td
                                key={s.strategy}
                                className={`tnum px-5 py-2.5 text-right font-mono ${
                                  s.strategy === "uplift"
                                    ? "bg-primary-soft/60"
                                    : ""
                                }`}
                              >
                                {s.measured_incremental_response != null ? (
                                  pp(s.measured_incremental_response)
                                ) : (
                                  <span className="font-sans text-[12px] text-mute">
                                    Not available
                                  </span>
                                )}
                              </td>
                            ))}
                          </tr>
                          <tr className="border-b border-line/70">
                            <th
                              scope="row"
                              className="px-5 py-2.5 text-left font-normal text-ink-2"
                            >
                              Cost per incremental txn
                            </th>
                            {strategies.map((s) => (
                              <td
                                key={s.strategy}
                                className={`tnum px-5 py-2.5 text-right font-mono ${
                                  s.strategy === "uplift"
                                    ? "bg-primary-soft/60"
                                    : ""
                                }`}
                              >
                                {s.cost_per_incremental_txn_bdt != null ? (
                                  bdt(s.cost_per_incremental_txn_bdt)
                                ) : (
                                  <span className="font-sans text-[12px] text-mute">
                                    Not available
                                  </span>
                                )}
                              </td>
                            ))}
                          </tr>
                        </>
                      ) : (
                        <tr>
                          <td
                            colSpan={strategies.length + 1}
                            className="px-5 py-4 text-[12.5px] text-ink-2"
                          >
                            <span className="font-medium text-warn">
                              No measured results.
                            </span>{" "}
                            The backend has not supplied holdout measurements
                            for these strategies. Expected values above are
                            model estimates and have not been validated on test.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </Panel>

              <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
                <Panel className="p-5">
                  <SectionHeader
                    title="Comparative expected incremental value"
                    meta="Backend estimates"
                  />
                  <StrategyBars strategies={strategies} />
                </Panel>
                <Panel className="p-5">
                  <SectionHeader title="Reading this comparison" />
                  <ul className="space-y-3 text-[13px] leading-relaxed text-ink-2">
                    <li>
                      <span className="font-medium text-ink">
                        Response-based
                      </span>{" "}
                      targets customers with high conversion likelihood
                      regardless of incentive, meaning many would have converted
                      anyway.
                    </li>
                    <li>
                      <span className="font-medium text-ink">
                        Uplift targeting
                      </span>{" "}
                      isolates incremental conversions caused directly by the
                      incentive, filtering out both sure things and potential
                      negative uplift (sleeping dogs).
                    </li>
                    <li>
                      <span className="font-medium text-ink">
                        Random allocation
                      </span>{" "}
                      provides the empirical baseline that any targeting model
                      must outperform.
                    </li>
                  </ul>
                </Panel>
              </div>
            </>
          )
        })()}
    </div>
  )
}
