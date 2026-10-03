import { useEffect, useState } from "react"
import {
  apiClient,
  ApiError,
  type CampaignResponse,
  type OptimizeResponse,
  type StrategyMetricItem,
  type StrategyName,
} from "../api/client"
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  FormField,
  LoadingState,
  MetricBlock,
  PageHeader,
  Panel,
  SectionHeader,
  inputCls,
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

function AllocationBar({ o }: { o: OptimizeResponse }) {
  const total = Math.max(o.selected_count + o.customers_excluded_negative, 1)
  const selPct = Math.max((o.selected_count / total) * 100, 0)
  const excPct = Math.max((o.customers_excluded_negative / total) * 100, 0)

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1.5 flex justify-between text-[12.5px]">
          <span className="font-medium text-ink">
            Selected vs Excluded Audience
          </span>
          <span className="tnum font-mono text-mute">
            <span className="font-semibold text-primary">
              {num(o.selected_count)}
            </span>{" "}
            of {num(o.selected_count + o.customers_excluded_negative)} evaluated
          </span>
        </div>
        <div
          className="flex h-5 w-full bg-sunken rounded-xs overflow-hidden"
          role="img"
          aria-label={`Audience allocation: ${num(o.selected_count)} selected, ${num(o.customers_excluded_negative)} excluded`}
        >
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${selPct}%` }}
            title={`Selected within budget: ${num(o.selected_count)}`}
          />
          <div
            className="h-full bg-neg/40 transition-all duration-300"
            style={{ width: `${excPct}%` }}
            title={`Excluded negative uplift: ${num(o.customers_excluded_negative)}`}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-[12px] border-t border-line/60">
        <div className="flex items-start gap-2">
          <span className="size-2.5 mt-1 bg-primary rounded-xs shrink-0" />
          <div>
            <p className="font-medium text-ink">Selected for Offer</p>
            <p className="font-mono text-mute">
              {num(o.selected_count)} customers
            </p>
            <p className="font-mono text-[11px] text-mute">
              {bdt(o.spend_bdt)} allocated
            </p>
          </div>
        </div>
        <div className="flex items-start gap-2">
          <span className="size-2.5 mt-1 bg-neg/40 rounded-xs shrink-0" />
          <div>
            <p className="font-medium text-ink">Negative Uplift Avoided</p>
            <p className="font-mono text-mute">
              {num(o.customers_excluded_negative)} customers
            </p>
            <p className="text-[11px] text-mute">
              Protected from negative effect
            </p>
          </div>
        </div>
        <div className="flex items-start gap-2">
          <span className="size-2.5 mt-1 bg-pos rounded-xs shrink-0" />
          <div>
            <p className="font-medium text-ink">Incremental Outcome</p>
            <p className="font-mono text-pos font-semibold">
              +{o.expected_incremental_value.toFixed(2)}
            </p>
            <p className="text-[11px] text-mute">Expected value (not ROI)</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComparisonTable({ strategies }: { strategies: StrategyMetricItem[] }) {
  const hasMeasured = strategies.some(
    (s) =>
      s.measured_incremental_response != null ||
      s.cost_per_incremental_txn_bdt != null,
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-[13px]">
        <caption className="sr-only">
          Strategy comparison at current budget
        </caption>
        <thead>
          <tr className="border-b border-line-strong">
            <th
              scope="col"
              className="w-[28%] px-4 py-2.5 text-left align-bottom text-[11.5px] font-medium text-mute"
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
                  className={`px-4 py-2.5 text-right align-bottom ${
                    isUplift ? "bg-primary-soft/60" : ""
                  }`}
                >
                  <div className="flex flex-col items-end gap-1">
                    <span className="flex items-center justify-end gap-1.5 text-[13px] font-semibold text-ink">
                      {isUplift && (
                        <Badge tone="primary" dot={false}>
                          Selected
                        </Badge>
                      )}
                      {cfg.label}
                    </span>
                    <span className="text-[11px] font-normal text-mute">
                      {cfg.ranks_by}
                    </span>
                  </div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-line/60">
            <th
              scope="row"
              className="px-4 py-2 text-left font-normal text-ink-2"
            >
              Selected customers
            </th>
            {strategies.map((s) => (
              <td
                key={s.strategy}
                className={`tnum px-4 py-2 text-right font-mono ${
                  s.strategy === "uplift"
                    ? "bg-primary-soft/60 font-semibold"
                    : ""
                }`}
              >
                {num(s.selected_count)}
              </td>
            ))}
          </tr>
          <tr className="border-b border-line/60">
            <th
              scope="row"
              className="px-4 py-2 text-left font-normal text-ink-2"
            >
              Actual spend
            </th>
            {strategies.map((s) => (
              <td
                key={s.strategy}
                className={`tnum px-4 py-2 text-right font-mono ${
                  s.strategy === "uplift" ? "bg-primary-soft/60" : ""
                }`}
              >
                {bdt(s.spend_bdt)}
              </td>
            ))}
          </tr>
          <tr className="border-b border-line/60">
            <th
              scope="row"
              className="px-4 py-2 text-left font-medium text-ink"
            >
              Expected incremental value
            </th>
            {strategies.map((s) => (
              <td
                key={s.strategy}
                className={`tnum px-4 py-2 text-right font-mono ${
                  s.strategy === "uplift"
                    ? "bg-primary-soft/60 font-semibold text-pos"
                    : ""
                }`}
              >
                {s.expected_incremental_value.toFixed(2)}
              </td>
            ))}
          </tr>
          <tr className="border-b border-line/60">
            <th
              scope="row"
              className="px-4 py-2 text-left font-normal text-ink-2"
            >
              Negative uplift share
            </th>
            {strategies.map((s) => (
              <td
                key={s.strategy}
                className={`tnum px-4 py-2 text-right font-mono ${
                  s.strategy === "uplift" ? "bg-primary-soft/60" : ""
                }`}
              >
                {pct(s.negative_uplift_selected_share)}
              </td>
            ))}
          </tr>
          <tr className="border-b border-line/60">
            <th
              scope="row"
              className="px-4 py-2 text-left font-normal text-ink-2"
            >
              Support
            </th>
            {strategies.map((s) => (
              <td
                key={s.strategy}
                className={`px-4 py-2 text-right ${
                  s.strategy === "uplift" ? "bg-primary-soft/60" : ""
                }`}
              >
                <Badge
                  tone={s.support === "sufficient" ? "pos" : "warn"}
                  dot={false}
                >
                  {s.support === "sufficient" ? "Sufficient" : "Insufficient"}
                </Badge>
              </td>
            ))}
          </tr>
          {hasMeasured && (
            <>
              <tr className="border-b border-line/60">
                <th
                  scope="row"
                  className="px-4 py-2 text-left font-normal text-ink-2"
                >
                  Measured incremental response
                </th>
                {strategies.map((s) => (
                  <td
                    key={s.strategy}
                    className={`tnum px-4 py-2 text-right font-mono ${
                      s.strategy === "uplift" ? "bg-primary-soft/60" : ""
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
              <tr className="border-b border-line/60">
                <th
                  scope="row"
                  className="px-4 py-2 text-left font-normal text-ink-2"
                >
                  Cost per incremental txn
                </th>
                {strategies.map((s) => (
                  <td
                    key={s.strategy}
                    className={`tnum px-4 py-2 text-right font-mono ${
                      s.strategy === "uplift" ? "bg-primary-soft/60" : ""
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
          )}
        </tbody>
      </table>
    </div>
  )
}

export default function BudgetOptimization() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id") || query.get("id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [campaign, setCampaign] = useState<CampaignResponse | null>(null)
  const [budget, setBudget] = useState<number>(0)
  const [excludeNegative, setExcludeNegative] = useState<boolean>(true)
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">(
    "idle",
  )
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [ranFor, setRanFor] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Synchronize campaign ID if present in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Fetch campaign definition on mount or activeId change
  useEffect(() => {
    if (!activeId) {
      setCampaign(null)
      setResult(null)
      setStatus("idle")
      setError(null)
      return
    }

    let alive = true
    apiClient
      .getCampaign(activeId)
      .then((res) => {
        if (!alive) return
        setCampaign(res)
        setBudget(res.budget_bdt)
      })
      .catch(() => {
        // If campaign load fails, user can still enter custom budget
      })

    return () => {
      alive = false
    }
  }, [activeId])

  const execute = async () => {
    if (!activeId) return
    setStatus("running")
    setError(null)

    try {
      const res = await apiClient.optimizeBudget(activeId, {
        budget_bdt: budget,
        exclude_negative_uplift: excludeNegative,
      })
      setResult(res)
      setRanFor(budget)
      setStatus("done")
    } catch (err: unknown) {
      let msg = "The optimization service failed."
      if (err instanceof ApiError) {
        msg = err.errorResponse?.message || err.message
        if (err.errorResponse?.detail) {
          msg += ` (${err.errorResponse.detail})`
        }
      } else if (err instanceof Error) {
        msg = err.message
      }
      setError(msg)
      setStatus("error")
    }
  }

  const stale = result && ranFor !== budget
  const upliftStrategy = result?.comparison?.strategies?.find(
    (s) => s.strategy === "uplift",
  )
  const isInsufficient = upliftStrategy?.support === "insufficient"

  return (
    <div className="space-y-6">
      <PageHeader
        step="06"
        title="Budget Optimization"
        lede="Allocate the budget to customers where the offer is expected to create the most incremental response. All outputs are expected values from the backend optimizer."
      />

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Panel className="p-5 lg:self-start">
          <SectionHeader title="Optimizer Inputs" />
          <div className="space-y-4">
            <div>
              <p className="text-[12px] font-medium text-mute uppercase tracking-wider">
                Active Campaign
              </p>
              <p className="text-[13.5px] font-semibold text-ink truncate">
                {campaign ? campaign.name : activeId || "None selected"}
              </p>
              {campaign && (
                <p className="font-mono text-[11.5px] text-mute">
                  Unit offer cost: {bdt(campaign.incentive_cost_bdt)}
                </p>
              )}
            </div>

            <FormField
              id="budget-input"
              label="Optimization budget (৳)"
              required
              hint={
                campaign
                  ? `Configured in setup: ${bdt(campaign.budget_bdt)}`
                  : "Target spend limit"
              }
            >
              <input
                id="budget-input"
                type="number"
                min={0}
                className={`${inputCls()} tnum font-mono`}
                value={budget || ""}
                onChange={(e) => setBudget(Number(e.target.value))}
                placeholder="500000"
              />
            </FormField>

            {campaign && budget > campaign.budget_bdt && (
              <p className="text-[12px] text-warn">
                Exceeds campaign configured budget of {bdt(campaign.budget_bdt)}
                .
              </p>
            )}

            <div className="pt-1">
              <label className="flex items-start gap-2 text-[12.5px] text-ink cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="mt-0.5 rounded-xs border-line text-primary focus:ring-primary/30"
                  checked={excludeNegative}
                  onChange={(e) => setExcludeNegative(e.target.checked)}
                />
                <span>
                  <strong className="font-medium">
                    Exclude potential negative uplift
                  </strong>
                  <span className="block text-[11.5px] text-mute">
                    Filter out customers with predicted uplift &lt; 0 (sleeping
                    dogs).
                  </span>
                </span>
              </label>
            </div>

            <div className="text-[12px] border-t border-line/60 pt-3">
              <p className="font-medium text-ink mb-1.5">Optimizer Policy</p>
              <ul className="space-y-1 text-ink-2">
                <li>· Greedy knapsack algorithm</li>
                <li>· Ranked by predicted causal uplift</li>
                <li>· Zero client-side ROI calculation</li>
                <li>· Actual spend sourced from backend</li>
              </ul>
            </div>

            <Button
              variant="primary"
              className="w-full"
              onClick={execute}
              disabled={status === "running" || !activeId}
            >
              {status === "running"
                ? "Running optimization…"
                : result
                  ? "Re-run optimization"
                  : "Run optimization"}
            </Button>
          </div>
        </Panel>

        <Panel>
          {!activeId && (
            <EmptyState
              title="No active campaign"
              action={
                <Button variant="primary" onClick={() => navigate("/setup")}>
                  Go to Campaign Setup
                </Button>
              }
            >
              Select or configure a campaign first to run budget optimization.
            </EmptyState>
          )}

          {activeId && status === "idle" && !result && (
            <EmptyState title="Optimization not yet run">
              Set the optimization budget and click &ldquo;Run
              optimization&rdquo; to execute the greedy knapsack solver against
              the scored audience.
            </EmptyState>
          )}

          {activeId && status === "running" && (
            <LoadingState
              rows={6}
              label="Executing backend budget optimization"
            />
          )}

          {activeId && status === "error" && (
            <ErrorState message={error} onRetry={execute} />
          )}

          {activeId && result && (
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-[13px] font-semibold tracking-wide uppercase text-ink">
                    Recommended Allocation
                  </h2>
                  <Badge tone="pos">Optimal</Badge>
                </div>
                {stale && (
                  <span className="text-[12px] text-warn">
                    Result reflects {bdt(ranFor)} — re-run to update.
                  </span>
                )}
              </div>

              {isInsufficient && (
                <div className="m-5 border-l-2 border-warn bg-warn-soft/40 p-4">
                  <p className="text-[13px] font-semibold text-warn">
                    Insufficient Support
                  </p>
                  <p className="mt-1 text-[12.5px] text-ink-2">
                    The optimizer reports insufficient support for this budget
                    allocation. Estimates have high variance; consider adjusting
                    the budget or targeting criteria.
                  </p>
                </div>
              )}

              <dl className="grid grid-cols-2 gap-x-6 gap-y-5 border-b border-line p-5 md:grid-cols-4">
                <MetricBlock
                  label="Selected audience"
                  value={num(result.selected_count)}
                  note="Targeted customers"
                />
                <MetricBlock
                  label="Actual spend"
                  value={bdt(result.spend_bdt)}
                  note={`of ${bdt(result.budget_bdt)} budget (${pct(
                    result.spend_bdt / (result.budget_bdt || 1),
                  )})`}
                />
                <MetricBlock
                  label="Expected incremental value"
                  value={result.expected_incremental_value.toFixed(2)}
                  tone="pos"
                  note="Expected value — not ROI"
                />
                <MetricBlock
                  label="Excluded negative uplift"
                  value={num(result.customers_excluded_negative)}
                  note="Customers filtered out"
                />
              </dl>

              <div className="p-5 border-b border-line">
                <SectionHeader title="Audience allocation breakdown" />
                <AllocationBar o={result} />
              </div>

              {result.comparison?.strategies && (
                <div className="p-5 border-b border-line">
                  <SectionHeader
                    title="Strategy comparison under this budget"
                    meta="Side-by-side evaluation"
                  />
                  <ComparisonTable strategies={result.comparison.strategies} />
                </div>
              )}

              <div className="p-5">
                <SectionHeader title="Optimization constraints applied" />
                <table className="w-full text-[12.5px]">
                  <caption className="sr-only">
                    Optimization constraints
                  </caption>
                  <tbody>
                    <tr className="border-b border-line/60">
                      <th
                        scope="row"
                        className="py-2 text-left font-normal text-ink-2"
                      >
                        Budget constraint
                      </th>
                      <td className="tnum py-2 font-mono text-ink">
                        {bdt(result.budget_bdt)}
                      </td>
                      <td className="py-2 text-right">
                        {result.spend_bdt >= result.budget_bdt ? (
                          <Badge tone="warn">Binding</Badge>
                        ) : (
                          <span className="text-mute">Not binding</span>
                        )}
                      </td>
                    </tr>
                    <tr className="border-b border-line/60">
                      <th
                        scope="row"
                        className="py-2 text-left font-normal text-ink-2"
                      >
                        Exclude potential negative uplift
                      </th>
                      <td className="tnum py-2 font-mono text-ink">
                        {excludeNegative ? "Active" : "Disabled"}
                      </td>
                      <td className="py-2 text-right">
                        {result.customers_excluded_negative > 0 ? (
                          <Badge tone="primary">
                            {num(result.customers_excluded_negative)} excluded
                          </Badge>
                        ) : (
                          <span className="text-mute">0 excluded</span>
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
                <p className="mt-3 text-[12px] text-mute">
                  &ldquo;Binding&rdquo; indicates the budget limit constrained
                  customer selection. All spend and impact figures are generated
                  directly by the backend knapsack optimizer.
                </p>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
