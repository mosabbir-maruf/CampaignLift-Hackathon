import { useState } from "react"
import { DEMO_EXPLANATIONS } from "../api/demo"
import { useResource } from "../hooks/useResource"
import {
  Badge,
  Button,
  DumbbellLegend,
  EmptyState,
  IllustrativeTag,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  Resource,
  SectionHeader,
  StatusBadge,
  UpliftIndicator,
  inputCls,
} from "../components/ui"
import { navigate, useRoute } from "../lib/router"
import { pct, pp, type Tone } from "../lib/format"

const DECISION: Record<string, { label: string tone: Tone }> = {
  prioritize: { label: "Prioritize", tone: "pos" },
  do_not_prioritize: { label: "Do not prioritize", tone: "neg" },
  review: { label: "Review", tone: "warn" },
}

export default function CustomerExplanation() {
  const { query } = useRoute()
  const id = query.get("id") ?? "CUS-10482"
  const [lookup, setLookup] = useState(id)
  const r = useResource(DEMO_EXPLANATIONS)
  const ex = r.data?.[id]

  return (
    <div className="space-y-6">
      <PageHeader
        step="07"
        title="Customer Explanation"
        lede="Why the model suggests a decision for one customer. Contributions show signals associated with the prediction — they are not causes."
        actions={
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              navigate(`/explain?id=${lookup.trim().toUpperCase()}`)
            }}
          >
            <label className="sr-only" htmlFor="cid">
              Customer ID
            </label>
            <input
              id="cid"
              value={lookup}
              onChange={(e) => setLookup(e.target.value)}
              className={`${inputCls()} h-8 w-36 font-mono text-[12.5px]`}
            />
            <Button type="submit">Load</Button>
          </form>
        }
      />

      <div className="flex flex-wrap gap-2 text-[12px]">
        <span className="text-mute">Examples:</span>
        {Object.keys(DEMO_EXPLANATIONS).map((k) => (
          <button
            key={k}
            onClick={() => {
              setLookup(k)
              navigate(`/explain?id=${k}`)
            }}
            className={`rounded-[3px] px-1.5 font-mono ${
              k === id ? "bg-ink text-white" : "text-primary hover:underline"
            }`}
          >
            {k}
          </button>
        ))}
        <IllustrativeTag show={r.illustrative} />
      </div>

      <Resource r={r} rows={8}>
        {() =>
          !ex ? (
            <Panel>
              <EmptyState title={`No explanation for ${id}`}>
                The backend returned no explanation for this customer. Check the
                ID or pick a customer from Audience.
              </EmptyState>
            </Panel>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[1fr_1.25fr]">
              <Panel>
                <div className="border-b border-line p-5">
                  <p className="font-mono text-[12px] text-mute">
                    {ex.customer_id}
                  </p>
                  <p className="mt-3 text-[11.5px] text-mute">
                    Targeting decision
                  </p>
                  <p
                    className={`mt-0.5 flex items-center gap-2 text-[22px] font-semibold tracking-tight ${
                      DECISION[ex.decision].tone === "pos"
                        ? "text-pos"
                        : DECISION[ex.decision].tone === "neg"
                          ? "text-neg"
                          : "text-warn"
                    }`}
                  >
                    <span aria-hidden className="text-[14px]">
                      {ex.decision === "prioritize"
                        ? "●"
                        : ex.decision === "review"
                          ? "◐"
                          : "○"}
                    </span>
                    {DECISION[ex.decision].label}
                  </p>
                  <div className="mt-2">
                    <StatusBadge status={ex.targeting_status} />
                  </div>
                </div>
                <div className="space-y-4 p-5">
                  <dl className="grid grid-cols-3 gap-3">
                    <div>
                      <dt className="text-[11.5px] text-mute">Treatment</dt>
                      <dd className="tnum mt-1 font-mono text-[20px]">
                        {pct(ex.p_treat, 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[11.5px] text-mute">Control</dt>
                      <dd className="tnum mt-1 font-mono text-[20px] text-ink-2">
                        {pct(ex.p_control, 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[11.5px] text-mute">Uplift</dt>
                      <dd className="mt-1">
                        <UpliftIndicator value={ex.uplift} size="lg" />
                      </dd>
                    </div>
                  </dl>
                  <ProbabilityDumbbell
                    pTreat={ex.p_treat}
                    pControl={ex.p_control}
                    height="lg"
                    axis
                  />
                  <DumbbellLegend />
                </div>
                <div className="border-t border-line p-5">
                  <p className="text-[11.5px] text-mute">Reason code</p>
                  <p className="mt-1 font-mono text-[12.5px]">
                    {ex.reason_code}
                  </p>
                  <p className="mt-1 text-[13.5px]">{ex.reason_text}</p>
                </div>
              </Panel>

              <div className="space-y-6">
                <Panel className="p-5">
                  <SectionHeader
                    title="Contributing factors"
                    meta="Model contribution to uplift"
                  />
                  <ContributionChart items={ex.contributions} />
                </Panel>
                <aside className="rounded-[5px] border border-line bg-paper p-4 text-[12.5px] leading-relaxed text-ink-2">
                  <p className="font-semibold text-ink">How to read this</p>
                  <ul className="mt-1.5 list-disc space-y-1 pl-4">
                    <li>
                      Contributions describe how the model arrived at its
                      estimate for this customer. They are not proof that a
                      factor causes the response.
                    </li>
                    <li>
                      Probabilities are model estimates and carry uncertainty.
                      Use this view to review decisions, not to justify them
                      alone.
                    </li>
                    <li>
                      If the explanation looks wrong, flag the customer for
                      review rather than overriding scores in the frontend.
                    </li>
                  </ul>
                </aside>
              </div>
            </div>
          )
        }
      </Resource>
    </div>
  )
}

function ContributionChart({
  items,
}: {
  items: { feature: string label: string value: string contribution: number }[]
}) {
  const max = Math.max(...items.map((i) => Math.abs(i.contribution)), 0.01)
  return (
    <ul className="space-y-2.5">
      {items.map((i) => {
        const w = (Math.abs(i.contribution) / max) * 50
        const pos = i.contribution >= 0
        return (
          <li
            key={i.feature}
            className="grid grid-cols-[1fr] gap-1 md:grid-cols-[minmax(0,190px)_1fr_70px] md:items-center md:gap-3"
          >
            <div className="min-w-0">
              <p className="truncate text-[13px]">{i.label}</p>
              <p className="tnum font-mono text-[11px] text-mute">{i.value}</p>
            </div>
            <div
              className="relative h-4"
              role="img"
              aria-label={`${i.label}: ${pp(i.contribution)} ${
                pos ? "toward" : "against"
              } uplift`}
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-ink-2" />
              <div
                className={`absolute inset-y-0.5 ${pos ? "bg-pos" : "bg-neg"}`}
                style={
                  pos
                    ? { left: "50%", width: `${w}%` }
                    : { right: "50%", width: `${w}%` }
                }
              />
            </div>
            <p
              className={`tnum text-right font-mono text-[12px] ${
                pos ? "text-pos" : "text-neg"
              }`}
            >
              {pp(i.contribution)}
            </p>
          </li>
        )
      })}
      <li className="flex justify-between border-t border-line pt-2 text-[11px] text-mute">
        <span>← Lowers estimated uplift</span>
        <Badge tone="neu" dot={false}>
          Signals, not causes
        </Badge>
        <span>Raises estimated uplift →</span>
      </li>
    </ul>
  )
}
