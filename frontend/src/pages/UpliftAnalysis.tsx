import { DEMO_CUSTOMERS, DEMO_DECILES } from "../api/demo"
import { useResource } from "../hooks/useResource"
import DecileChart from "../components/DecileChart"
import {
  DumbbellLegend,
  IllustrativeTag,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  Resource,
  SectionHeader,
  StatusBadge,
  UpliftIndicator,
} from "../components/ui"
import { Link } from "../lib/router"
import { pct } from "../lib/format"

const EXAMPLES = ["CUS-20915", "CUS-10482", "CUS-31077"]
const CAPTION: Record<string, string> = {
  "CUS-20915": "Would respond anyway. The offer adds little.",
  "CUS-10482": "Persuadable. The offer is expected to change behaviour.",
  "CUS-31077": "Contact may reduce response. Do not target.",
}

export default function UpliftAnalysis() {
  const r = useResource({
    deciles: DEMO_DECILES,
    examples: DEMO_CUSTOMERS.filter((c) => EXAMPLES.includes(c.customer_id)),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        step="04"
        title="Uplift Analysis"
        lede="Uplift estimates the expected incremental response from treatment compared with no treatment: p_treat − p_control."
        actions={<IllustrativeTag show={r.illustrative} />}
      />

      <Resource r={r} rows={8}>
        {({ deciles, examples }) => (
          <>
            <Panel>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
                <h2 className="text-[13px] font-semibold tracking-wide uppercase">
                  Same offer, three outcomes
                </h2>
                <DumbbellLegend />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-[13px]">
                  <caption className="sr-only">
                    Treatment, control and uplift for example customers
                  </caption>
                  <thead>
                    <tr className="border-b border-line text-[11.5px] text-mute">
                      <th
                        scope="col"
                        className="px-5 py-2 text-left font-medium"
                      >
                        Customer
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2 text-right font-medium"
                      >
                        Treatment
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2 text-right font-medium"
                      >
                        Control
                      </th>
                      <th
                        scope="col"
                        className="w-[34%] px-3 py-2 text-left font-medium"
                      >
                        Response probability, 0–100%
                      </th>
                      <th
                        scope="col"
                        className="px-5 py-2 text-right font-medium"
                      >
                        Uplift
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {EXAMPLES.map(
                      (id) => examples.find((e) => e.customer_id === id)!,
                    )
                      .filter(Boolean)
                      .map((c) => (
                        <tr
                          key={c.customer_id}
                          className="border-b border-line/70 last:border-0"
                        >
                          <td className="px-5 py-4 align-top">
                            <Link
                              to={`/explain?id=${c.customer_id}`}
                              className="font-mono text-[13px] hover:text-primary hover:underline"
                            >
                              {c.customer_id}
                            </Link>
                            <p className="mt-1 text-[12px] text-mute">
                              {CAPTION[c.customer_id]}
                            </p>
                            <div className="mt-1.5">
                              <StatusBadge status={c.targeting_status} short />
                            </div>
                          </td>
                          <td className="tnum px-3 py-4 text-right align-top font-mono text-[15px]">
                            {pct(c.p_treat, 0)}
                          </td>
                          <td className="tnum px-3 py-4 text-right align-top font-mono text-[15px] text-ink-2">
                            {pct(c.p_control, 0)}
                          </td>
                          <td className="px-3 py-4 align-top">
                            <ProbabilityDumbbell
                              pTreat={c.p_treat}
                              pControl={c.p_control}
                              height="lg"
                              axis
                            />
                          </td>
                          <td className="px-5 py-4 text-right align-top">
                            <UpliftIndicator value={c.uplift} size="lg" />
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-line bg-paper px-5 py-3 text-[12.5px] text-ink-2">
                A 93% responder is not the best target if they would respond at
                91% anyway. Rank by the length and direction of the line, not by
                where the black dot sits.
              </p>
            </Panel>

            <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
              <Panel className="p-5">
                <SectionHeader
                  title="Uplift distribution by decile"
                  meta="uplift_deciles · backend"
                />
                <DecileChart deciles={deciles} />
              </Panel>
              <Panel>
                <div className="px-5 pt-5">
                  <SectionHeader title="Decile detail" />
                </div>
                <table className="w-full text-[12.5px]">
                  <caption className="sr-only">Decile values</caption>
                  <thead>
                    <tr className="border-b border-line text-[11px] text-mute">
                      <th
                        scope="col"
                        className="px-5 py-1.5 text-left font-medium"
                      >
                        Decile
                      </th>
                      <th
                        scope="col"
                        className="px-2 py-1.5 text-right font-medium"
                      >
                        Treat
                      </th>
                      <th
                        scope="col"
                        className="px-2 py-1.5 text-right font-medium"
                      >
                        Control
                      </th>
                      <th
                        scope="col"
                        className="px-5 py-1.5 text-right font-medium"
                      >
                        Uplift
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {deciles.map((d) => (
                      <tr
                        key={d.decile}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="tnum px-5 py-1.5 font-mono">
                          D{d.decile}
                        </td>
                        <td className="tnum px-2 py-1.5 text-right font-mono">
                          {pct(d.mean_p_treat, 0)}
                        </td>
                        <td className="tnum px-2 py-1.5 text-right font-mono text-ink-2">
                          {pct(d.mean_p_control, 0)}
                        </td>
                        <td className="px-5 py-1.5 text-right">
                          <UpliftIndicator value={d.mean_uplift} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            </div>
          </>
        )}
      </Resource>
    </div>
  )
}
