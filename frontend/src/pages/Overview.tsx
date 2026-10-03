import {
  DEMO_AUDIENCE_SUMMARY,
  DEMO_CAMPAIGN,
  DEMO_DECILES,
  DEMO_EXPERIMENT,
  DEMO_OPTIMIZATION,
  DEMO_STRATEGIES,
} from "../api/demo"
import { useResource } from "../hooks/useResource"
import {
  Badge,
  IllustrativeTag,
  MetricBlock,
  PageHeader,
  Panel,
  Resource,
  SectionHeader,
} from "../components/ui"
import DecileChart from "../components/DecileChart"
import Composition from "../components/Composition"
import { Link } from "../lib/router"
import { bdt, num, pp } from "../lib/format"

const NEXT = [
  {
    to: "/audience",
    n: "03",
    t: "Inspect the scored audience",
    d: "Who is persuadable, who responds anyway, who to avoid.",
  },
  {
    to: "/strategy",
    n: "05",
    t: "Compare targeting strategies",
    d: "Response ranking vs uplift ranking at equal spend.",
  },
  {
    to: "/budget",
    n: "06",
    t: "Confirm the budget allocation",
    d: "Review constraints before approving the audience.",
  },
]

export default function Overview() {
  const r = useResource({
    campaign: DEMO_CAMPAIGN,
    summary: DEMO_AUDIENCE_SUMMARY,
    deciles: DEMO_DECILES,
    opt: DEMO_OPTIMIZATION,
    strategies: DEMO_STRATEGIES,
    exp: DEMO_EXPERIMENT,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        step="01"
        title="Overview"
        lede="Who should receive this incentive, and why. The model estimates the incremental effect of the offer for each eligible customer."
        actions={<IllustrativeTag show={r.illustrative} />}
      />
      <Panel>
        <Resource r={r} rows={8}>
          {({ campaign, summary, deciles, opt, strategies, exp }) => {
            const uplift = strategies.find((s) => s.strategy === "uplift")!
            const response = strategies.find((s) => s.strategy === "response")!
            return (
              <div className="grid lg:grid-cols-[1.35fr_1fr]">
                {/* Decision column */}
                <div className="border-b border-line p-5 lg:border-r lg:border-b-0 lg:p-6">
                  <p className="font-mono text-[11px] tracking-wider text-mute uppercase">
                    Decision pending
                  </p>
                  <h2 className="mt-2 max-w-xl text-[19px] leading-snug font-semibold tracking-tight">
                    Approve an uplift-targeted audience of{" "}
                    {num(opt.selected_customers)} customers within the{" "}
                    {bdt(opt.budget)} budget?
                  </h2>
                  <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-ink-2">
                    The backend's current suggestion ranks customers by expected
                    incremental response, excludes {num(opt.excluded_negative)}{" "}
                    customers with potential negative uplift, and holds back
                    those with insufficient support.
                  </p>

                  <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-line pt-5 sm:grid-cols-4">
                    <MetricBlock
                      label="Eligible customers"
                      value={num(summary.eligible_customers)}
                    />
                    <MetricBlock
                      label="Suggested audience"
                      value={num(opt.selected_customers)}
                      note={`of ${num(opt.prioritized_customers)} prioritized`}
                    />
                    <MetricBlock
                      label="Expected incremental conv."
                      value={num(opt.expected_incremental_conversions)}
                      tone="pos"
                      note="Expected, not measured"
                    />
                    <MetricBlock
                      label="Expected spend"
                      value={bdt(opt.expected_spend)}
                      note={`${((opt.expected_spend / opt.budget) * 100).toFixed(0)}% of budget`}
                    />
                  </dl>

                  <div className="mt-6 rounded-[4px] bg-paper p-4">
                    <p className="text-[12px] font-medium text-ink">
                      Why not target the most likely responders?
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                      At the same spend, response-based targeting is expected to
                      yield{" "}
                      <span className="tnum font-mono">
                        {num(
                          response.expected.expected_incremental_conversions,
                        )}
                      </span>{" "}
                      incremental conversions against{" "}
                      <span className="tnum font-mono text-pos">
                        {num(uplift.expected.expected_incremental_conversions)}
                      </span>{" "}
                      for uplift targeting — many likely responders would
                      convert without the offer.
                    </p>
                    <Link
                      to="/strategy"
                      className="mt-2 inline-block text-[12.5px] font-medium text-primary underline-offset-2 hover:underline"
                    >
                      Compare strategies →
                    </Link>
                  </div>
                </div>

                {/* Context column */}
                <dl className="divide-y divide-line text-[13px]">
                  {[
                    ["Objective", campaign.objective],
                    [
                      "Offer",
                      `${campaign.offer_type} · ${bdt(campaign.offer_value)} per customer`,
                    ],
                    ["Window", `${campaign.start_date} → ${campaign.end_date}`],
                    ["Strategy", "Uplift targeting"],
                    ["Eligibility", campaign.eligibility_context],
                    [
                      "Scored",
                      new Date(summary.scored_at).toUTCString().slice(5, 22) +
                        " UTC",
                    ],
                  ].map(([k, v]) => (
                    <div
                      key={k}
                      className="grid grid-cols-[110px_1fr] gap-3 px-5 py-2.5"
                    >
                      <dt className="text-mute">{k}</dt>
                      <dd className="text-ink">{v}</dd>
                    </div>
                  ))}
                  <div className="grid grid-cols-[110px_1fr] gap-3 px-5 py-2.5">
                    <dt className="text-mute">Validation</dt>
                    <dd className="flex flex-wrap items-center gap-2">
                      <Badge
                        tone={exp.support === "sufficient" ? "pos" : "warn"}
                      >
                        {exp.support === "sufficient"
                          ? "Sufficient support"
                          : "Limited support"}
                      </Badge>
                      <span className="text-mute">
                        {exp.experiment_id} · observed{" "}
                        {pp(exp.incremental_effect)}
                      </span>
                    </dd>
                  </div>
                </dl>

                <div className="border-t border-line p-5 lg:col-span-2 lg:p-6">
                  <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
                    <div>
                      <SectionHeader
                        title="Audience composition"
                        meta={
                          <Link
                            to="/audience"
                            className="text-primary hover:underline"
                          >
                            Open audience →
                          </Link>
                        }
                      />
                      <Composition summary={summary} />
                    </div>
                    <div>
                      <SectionHeader
                        title="Uplift by decile"
                        meta={
                          <Link
                            to="/uplift"
                            className="text-primary hover:underline"
                          >
                            Open analysis →
                          </Link>
                        }
                      />
                      <DecileChart deciles={deciles} compact />
                    </div>
                  </div>
                </div>
              </div>
            )
          }}
        </Resource>
      </Panel>

      <section aria-labelledby="next">
        <h2
          id="next"
          className="mb-3 text-[13px] font-semibold tracking-wide uppercase"
        >
          Inspect next
        </h2>
        <ol className="grid gap-px overflow-hidden rounded-[5px] border border-line bg-line md:grid-cols-3">
          {NEXT.map((s) => (
            <li key={s.to} className="bg-surface">
              <Link to={s.to} className="group block h-full p-4 hover:bg-paper">
                <span className="tnum font-mono text-[11px] text-mute">
                  {s.n}
                </span>
                <p className="mt-1 text-[14px] font-medium group-hover:text-primary">
                  {s.t} <span aria-hidden>→</span>
                </p>
                <p className="mt-1 text-[12.5px] text-mute">{s.d}</p>
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
