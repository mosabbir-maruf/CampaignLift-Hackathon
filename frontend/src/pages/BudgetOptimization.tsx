import { useState } from "react"
import { DEMO_OPTIMIZATION } from "../api/demo"
import type { OptimizationResult } from "../api/types"
import { usePreview } from "../hooks/useResource"
import { hasBackend } from "../api/client"
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  FormField,
  IllustrativeTag,
  InsufficientState,
  LoadingState,
  MetricBlock,
  PageHeader,
  Panel,
  SectionHeader,
  inputCls,
} from "../components/ui"
import { bdt, num } from "../lib/format"

type Run = {
  status: "idle" | "running" | "done" | "error" | "insufficient"
  result: OptimizationResult | null
  ranFor: number | null
}

function Funnel({ o }: { o: OptimizationResult }) {
  const steps = [
    {
      label: "Eligible population",
      n: o.eligible_customers,
      note: "Resolved by backend",
    },
    {
      label: "Prioritized",
      n: o.prioritized_customers,
      note: "Positive uplift with sufficient support",
    },
    {
      label: "Selected within budget",
      n: o.selected_customers,
      note: `${bdt(o.cost_per_offer)} per offer`,
    },
  ]
  return (
    <ol className="space-y-3" aria-label="Allocation funnel">
      {steps.map((s, i) => (
        <li
          key={s.label}
          className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 md:grid-cols-[180px_1fr_110px]"
        >
          <div>
            <p className="text-[13px] font-medium">
              <span className="tnum mr-2 font-mono text-[11px] text-mute">
                {i + 1}
              </span>
              {s.label}
            </p>
            <p className="text-[11.5px] text-mute">{s.note}</p>
          </div>
          <div className="order-last col-span-2 h-5 bg-sunken md:order-none md:col-span-1">
            <div
              className={`h-full ${
                i === 2
                  ? "bg-primary"
                  : i === 1
                    ? "bg-primary/45"
                    : "bg-line-strong"
              }`}
              style={{
                width: `${Math.max((s.n / o.eligible_customers) * 100, 0.6)}%`,
              }}
            />
          </div>
          <p className="tnum text-right font-mono text-[14px]">{num(s.n)}</p>
        </li>
      ))}
      <li className="grid grid-cols-[1fr_auto] items-center gap-4 border-t border-line pt-3 md:grid-cols-[180px_1fr_110px]">
        <p className="text-[13px] font-medium">
          <span className="tnum mr-2 font-mono text-[11px] text-mute">4</span>
          Expected incremental impact
        </p>
        <p className="hidden text-[12px] text-mute md:block">
          Conversions expected to occur because of the offer
        </p>
        <p className="tnum text-right font-mono text-[14px] text-pos">
          +{num(o.expected_incremental_conversions)}
        </p>
      </li>
    </ol>
  )
}

export default function BudgetOptimization() {
  const { state } = usePreview()
  const [budget, setBudget] = useState(500000)
  const [run, setRun] = useState<Run>({
    status: "idle",
    result: null,
    ranFor: null,
  })

  const execute = () => {
    setRun((r) => ({ ...r, status: "running" }))
    // TODO(integration): request optimization from the backend with { budget }.
    setTimeout(() => {
      if (state === "error")
        setRun({ status: "error", result: null, ranFor: null })
      else if (state === "insufficient")
        setRun({ status: "insufficient", result: null, ranFor: budget })
      else setRun({ status: "done", result: DEMO_OPTIMIZATION, ranFor: budget })
    }, 800)
  }

  const o = run.result
  const stale = o && run.ranFor !== budget

  return (
    <div className="space-y-6">
      <PageHeader
        step="06"
        title="Budget Optimization"
        lede="Allocate the budget to customers where the offer is expected to create the most incremental response. All outputs are expected values from the backend optimizer."
        actions={<IllustrativeTag show={!hasBackend && !!o} />}
      />

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <Panel className="p-5 lg:self-start">
          <SectionHeader title="Inputs" />
          <div className="space-y-4">
            <FormField
              id="budget-input"
              label="Campaign budget (৳)"
              required
              hint="Available: ৳500,000 from campaign setup."
            >
              <input
                id="budget-input"
                type="number"
                min={0}
                className={`${inputCls()} tnum font-mono`}
                value={budget || ""}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </FormField>
            <div className="text-[12.5px]">
              <p className="mb-1.5 font-medium">Constraints</p>
              <ul className="space-y-1 text-ink-2">
                <li>· Exclude potential negative uplift</li>
                <li>· Exclude insufficient support</li>
                <li>· Minimum uplift +5.0 pp</li>
              </ul>
            </div>
            <Button
              variant="primary"
              className="w-full"
              onClick={execute}
              disabled={run.status === "running" || !(budget > 0)}
            >
              {run.status === "running"
                ? "Optimizing…"
                : o
                  ? "Re-run optimization"
                  : "Run optimization"}
            </Button>
            {budget > 500000 && (
              <p className="text-[12px] text-warn">
                Exceeds the campaign's available budget.
              </p>
            )}
          </div>
        </Panel>

        <Panel>
          {run.status === "idle" && (
            <EmptyState title="No allocation yet">
              Set a budget and run the optimizer. The backend will return the
              selected audience, expected spend and expected incremental value.
            </EmptyState>
          )}
          {run.status === "running" && (
            <LoadingState rows={6} label="Running optimization" />
          )}
          {run.status === "error" && (
            <ErrorState
              message="The optimization service did not respond."
              onRetry={execute}
            />
          )}
          {run.status === "insufficient" && (
            <InsufficientState>
              The optimizer could not find enough customers with supported
              positive uplift for this budget. No allocation is recommended;
              consider a smaller budget or broader eligibility.
            </InsufficientState>
          )}
          {run.status === "done" && o && (
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-[13px] font-semibold tracking-wide uppercase">
                    Recommended allocation
                  </h2>
                  <Badge tone="pos">Optimal</Badge>
                </div>
                {stale && (
                  <span className="text-[12px] text-warn">
                    Result reflects {bdt(run.ranFor)} — re-run to update.
                  </span>
                )}
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-5 border-b border-line p-5 md:grid-cols-4">
                <MetricBlock
                  label="Selected audience"
                  value={num(o.selected_customers)}
                />
                <MetricBlock
                  label="Expected spend"
                  value={bdt(o.expected_spend)}
                  note={`of ${bdt(o.available_budget)} available`}
                />
                <MetricBlock
                  label="Expected incremental conv."
                  value={num(o.expected_incremental_conversions)}
                  tone="pos"
                />
                <MetricBlock
                  label="Expected incremental value"
                  value={bdt(o.expected_incremental_value)}
                  tone="pos"
                  note="Expected — not ROI"
                />
              </dl>
              <div className="p-5">
                <SectionHeader title="Budget → audience → impact" />
                <Funnel o={o} />
              </div>
              <div className="border-t border-line p-5">
                <SectionHeader title="Constraints applied" />
                <table className="w-full text-[12.5px]">
                  <caption className="sr-only">
                    Optimization constraints
                  </caption>
                  <tbody>
                    {o.constraints.map((c) => (
                      <tr
                        key={c.label}
                        className="border-b border-line/60 last:border-0"
                      >
                        <th scope="row" className="py-2 text-left font-normal">
                          {c.label}
                        </th>
                        <td className="tnum py-2 font-mono">{c.value}</td>
                        <td className="py-2 text-right">
                          {c.binding ? (
                            <Badge tone="warn">Binding</Badge>
                          ) : (
                            <span className="text-mute">Not binding</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-3 text-[12px] text-mute">
                  {num(o.excluded_negative)} customers with potential negative
                  uplift were excluded. "Binding" means the constraint limited
                  the result.
                </p>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
