import { DEMO_EXPERIMENT } from "../api/demo"
import type { ExperimentArm, ExperimentSegment } from "../api/types"
import { useResource } from "../hooks/useResource"
import {
  Badge,
  IllustrativeTag,
  PageHeader,
  Panel,
  Resource,
  SectionHeader,
  UpliftIndicator,
} from "../components/ui"
import { num, pct } from "../lib/format"

const SUPPORT = {
  sufficient: { tone: "pos" as const, label: "Sufficient support" },
  limited: { tone: "warn" as const, label: "Limited support" },
  insufficient: { tone: "warn" as const, label: "Insufficient support" },
}

function Arm({
  name,
  arm,
  kind,
}: {
  name: string
  arm: ExperimentArm
  kind: "treat" | "control"
}) {
  return (
    <div className="p-5">
      <p className="flex items-center gap-2 text-[12px] text-mute">
        <span
          className={`size-2.5 rounded-full ${
            kind === "treat" ? "bg-ink" : "border-2 border-ink-2"
          }`}
        />
        {name}
      </p>
      <p className="tnum mt-2 font-mono text-[24px]">
        {pct(arm.response_rate)}
      </p>
      <p className="text-[12px] text-mute">response rate</p>
      <p className="tnum mt-3 font-mono text-[12px] text-ink-2">
        {num(arm.conversions)} / {num(arm.population)} customers
      </p>
    </div>
  )
}

function SegmentRow({ s, max }: { s: ExperimentSegment max: number }) {
  const t = s.treatment.response_rate,
    c = s.control.response_rate
  return (
    <tr className="border-b border-line/70 last:border-0">
      <th scope="row" className="px-5 py-3 text-left font-medium">
        {s.segment}
      </th>
      <td className="tnum px-3 py-3 text-right font-mono text-ink-2">
        {num(s.treatment.population)} / {num(s.control.population)}
      </td>
      <td className="w-[30%] px-3 py-3">
        {t == null || c == null ? (
          <span className="text-[12px] text-warn">
            Rates withheld by backend
          </span>
        ) : (
          <div
            className="space-y-1"
            role="img"
            aria-label={`Treatment ${pct(t)}, control ${pct(c)}`}
          >
            <div className="flex items-center gap-2">
              <div
                className="h-2 bg-ink"
                style={{ width: `${(t / max) * 100}%` }}
              />
              <span className="tnum font-mono text-[11px]">{pct(t, 0)}</span>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="h-2 border border-ink-2 bg-surface"
                style={{ width: `${(c / max) * 100}%` }}
              />
              <span className="tnum font-mono text-[11px] text-mute">
                {pct(c, 0)}
              </span>
            </div>
          </div>
        )}
      </td>
      <td className="px-3 py-3 text-right">
        <UpliftIndicator value={s.incremental_effect} />
      </td>
      <td className="px-5 py-3 text-right">
        <Badge tone={SUPPORT[s.support].tone}>{SUPPORT[s.support].label}</Badge>
      </td>
    </tr>
  )
}

export default function ExperimentIntelligence() {
  const r = useResource(DEMO_EXPERIMENT)
  return (
    <div className="space-y-6">
      <PageHeader
        step="08"
        title="Experiment Intelligence"
        lede="Observed treatment and control outcomes from a randomized holdout. Shows evidence as reported — no significance or intervals unless the backend supplies them."
        actions={<IllustrativeTag show={r.illustrative} />}
      />
      <Resource r={r} rows={8}>
        {(e) => {
          const max = Math.max(
            ...e.segments.flatMap((s) => [
              s.treatment.response_rate ?? 0,
              s.control.response_rate ?? 0,
            ]),
            0.01,
          )
          return (
            <>
              <Panel>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
                  <p className="text-[13px]">
                    <span className="font-mono">{e.experiment_id}</span>{" "}
                    <span className="text-mute">· {e.period}</span>
                  </p>
                  <Badge tone={SUPPORT[e.support].tone}>
                    {SUPPORT[e.support].label}
                  </Badge>
                </div>
                <div className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
                  <Arm name="Treatment arm" arm={e.treatment} kind="treat" />
                  <Arm name="Control arm" arm={e.control} kind="control" />
                  <div className="p-5">
                    <p className="text-[12px] text-mute">
                      Observed incremental effect
                    </p>
                    <p className="mt-2">
                      <UpliftIndicator value={e.incremental_effect} size="lg" />
                    </p>
                    <p className="text-[12px] text-mute">
                      treatment − control response rate
                    </p>
                    <p className="mt-3 text-[12px] text-ink-2">
                      No significance test supplied.
                    </p>
                  </div>
                </div>
                {e.support_note && (
                  <p className="border-t border-line bg-warn-soft/60 px-5 py-2.5 text-[12.5px] text-ink-2">
                    <span className="font-medium text-warn">
                      Support note ·{" "}
                    </span>
                    {e.support_note}
                  </p>
                )}
              </Panel>

              <Panel>
                <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-5">
                  <SectionHeader title="Segment breakdown" />
                  <span className="mb-3 flex gap-3 text-[11.5px] text-mute">
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-3 bg-ink" />
                      Treatment
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-3 border border-ink-2" />
                      Control
                    </span>
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-[13px]">
                    <caption className="sr-only">
                      Experiment results by predicted uplift segment
                    </caption>
                    <thead>
                      <tr className="border-y border-line text-[11.5px] text-mute">
                        <th
                          scope="col"
                          className="px-5 py-2 text-left font-medium"
                        >
                          Predicted segment
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-2 text-right font-medium"
                        >
                          n treat / control
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-2 text-left font-medium"
                        >
                          Response rate
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-2 text-right font-medium"
                        >
                          Incremental
                        </th>
                        <th
                          scope="col"
                          className="px-5 py-2 text-right font-medium"
                        >
                          Support
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {e.segments.map((s) => (
                        <SegmentRow key={s.segment} s={s} max={max} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="border-t border-line px-5 py-3 text-[12px] text-mute">
                  If segments ordered by predicted uplift also show decreasing
                  observed effect, the model's ranking is consistent with the
                  test. This is a consistency check, not proof.
                </p>
              </Panel>
            </>
          )
        }}
      </Resource>
    </div>
  )
}
