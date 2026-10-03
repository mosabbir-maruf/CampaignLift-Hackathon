import { DEMO_STRATEGIES } from "../api/demo"
import type { StrategyMetrics, StrategyResult } from "../api/types"
import { useResource } from "../hooks/useResource"
import {
  Badge,
  IllustrativeTag,
  PageHeader,
  Panel,
  Resource,
  SectionHeader,
} from "../components/ui"
import { bdt, num } from "../lib/format"

const ROWS: {
  key: keyof StrategyMetrics
  label: string
  fmt: (v: number) => string
  emphasis?: boolean
}[] = [
  { key: "target_population", label: "Target population", fmt: num },
  { key: "expected_conversions", label: "Total conversions", fmt: num },
  {
    key: "expected_incremental_conversions",
    label: "Incremental conversions",
    fmt: num,
    emphasis: true,
  },
  {
    key: "expected_incremental_value",
    label: "Incremental value",
    fmt: bdt,
    emphasis: true,
  },
  { key: "spend", label: "Spend", fmt: bdt },
  {
    key: "incremental_per_1k_spend",
    label: "Incremental conv. per ৳1k",
    fmt: (v) => v.toFixed(2),
  },
]

function Bars({ data }: { data: StrategyResult[] }) {
  const max = Math.max(...data.map((s) => s.expected.expected_conversions))
  return (
    <div className="space-y-4">
      {data.map((s) => {
        const total = s.expected.expected_conversions
        const inc = s.expected.expected_incremental_conversions
        return (
          <div key={s.strategy}>
            <div className="mb-1 flex justify-between text-[12.5px]">
              <span className={s.strategy === "uplift" ? "font-semibold" : ""}>
                {s.label}
              </span>
              <span className="tnum font-mono text-mute">
                <span className="text-pos">{num(inc)}</span> of {num(total)}
              </span>
            </div>
            <div
              className="flex h-4 bg-sunken"
              style={{ width: `${(total / max) * 100}%` }}
              role="img"
              aria-label={`${s.label}: ${num(inc)} incremental of ${num(total)} expected conversions`}
            >
              <div
                className="h-full bg-pos"
                style={{ width: `${(inc / total) * 100}%` }}
              />
              <div className="h-full flex-1 bg-neu/35 [background-image:repeating-linear-gradient(-45deg,transparent_0_3px,rgba(255,255,255,.5)_3px_5px)]" />
            </div>
          </div>
        )
      })}
      <div className="flex flex-wrap gap-4 pt-1 text-[11.5px] text-mute">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 bg-pos" />
          Incremental — caused by the offer
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 bg-neu/35" />
          Would have converted anyway
        </span>
      </div>
    </div>
  )
}

export default function StrategyComparison() {
  const r = useResource(DEMO_STRATEGIES)
  return (
    <div className="space-y-6">
      <PageHeader
        step="05"
        title="Strategy Comparison"
        lede="Response prediction asks who will convert. Uplift prediction asks who will convert because of the offer. At equal spend, these choose different customers."
        actions={<IllustrativeTag show={r.illustrative} />}
      />
      <Resource r={r} rows={8}>
        {(data) => {
          const hasMeasured = data.some((s) => s.measured)
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
                        {data.map((s) => (
                          <th
                            key={s.strategy}
                            scope="col"
                            className={`px-5 py-3 text-right align-bottom ${
                              s.strategy === "uplift"
                                ? "bg-primary-soft/60"
                                : ""
                            }`}
                          >
                            <span className="flex items-center justify-end gap-2 text-[13.5px] font-semibold">
                              {s.strategy === "uplift" && (
                                <Badge tone="primary" dot={false}>
                                  Selected
                                </Badge>
                              )}
                              {s.label}
                            </span>
                            <span className="mt-1 block text-[11.5px] font-normal text-mute">
                              {s.ranks_by}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th
                          colSpan={4}
                          scope="colgroup"
                          className="bg-paper px-5 py-1.5 text-left font-mono text-[10.5px] font-medium tracking-wider text-mute uppercase"
                        >
                          Expected · model estimate
                        </th>
                      </tr>
                      {ROWS.map((row) => (
                        <tr key={row.key} className="border-b border-line/70">
                          <th
                            scope="row"
                            className={`px-5 py-2.5 text-left font-normal ${
                              row.emphasis
                                ? "font-medium text-ink"
                                : "text-ink-2"
                            }`}
                          >
                            {row.label}
                          </th>
                          {data.map((s) => (
                            <td
                              key={s.strategy}
                              className={`tnum px-5 py-2.5 text-right font-mono ${
                                s.strategy === "uplift"
                                  ? "bg-primary-soft/60"
                                  : ""
                              } ${
                                row.emphasis && s.strategy === "uplift"
                                  ? "font-semibold text-pos"
                                  : ""
                              }`}
                            >
                              {row.fmt(s.expected[row.key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                      <tr>
                        <th
                          colSpan={4}
                          scope="colgroup"
                          className="bg-paper px-5 py-1.5 text-left font-mono text-[10.5px] font-medium tracking-wider text-mute uppercase"
                        >
                          Measured on test · holdout
                        </th>
                      </tr>
                      {hasMeasured ? (
                        ROWS.slice(1, 4).map((row) => (
                          <tr key={row.key} className="border-b border-line/70">
                            <th
                              scope="row"
                              className="px-5 py-2.5 text-left font-normal text-ink-2"
                            >
                              {row.label}
                            </th>
                            {data.map((s) => {
                              const v = s.measured?.[row.key]
                              return (
                                <td
                                  key={s.strategy}
                                  className="tnum px-5 py-2.5 text-right font-mono"
                                >
                                  {v == null ? (
                                    <span className="font-sans text-[12px] text-mute">
                                      Not available
                                    </span>
                                  ) : (
                                    row.fmt(v)
                                  )}
                                </td>
                              )
                            })}
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            colSpan={4}
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
                    title="Where expected conversions come from"
                    meta="Expected"
                  />
                  <Bars data={data} />
                </Panel>
                <Panel className="p-5">
                  <SectionHeader title="Reading this comparison" />
                  <ul className="space-y-3 text-[13px] leading-relaxed text-ink-2">
                    <li>
                      <span className="font-medium text-ink">
                        Response-based
                      </span>{" "}
                      has the most total conversions — mostly customers who
                      would have converted without the offer. Spend goes to them
                      anyway.
                    </li>
                    <li>
                      <span className="font-medium text-ink">
                        Uplift targeting
                      </span>{" "}
                      has fewer total conversions but more that are caused by
                      the offer.
                    </li>
                    <li>
                      <span className="font-medium text-ink">Random</span> is
                      the baseline any strategy should beat.
                    </li>
                  </ul>
                </Panel>
              </div>
            </>
          )
        }}
      </Resource>
    </div>
  )
}
