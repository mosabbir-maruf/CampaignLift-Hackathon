import { useMemo, useState } from "react"
import { DEMO_AUDIENCE_SUMMARY, DEMO_CUSTOMERS } from "../api/demo"
import type { ScoredCustomer, TargetingStatus } from "../api/types"
import { useResource } from "../hooks/useResource"
import DataTable, { type Column } from "../components/DataTable"
import Composition from "../components/Composition"
import {
  Button,
  Drawer,
  DumbbellLegend,
  EmptyState,
  IllustrativeTag,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  Resource,
  StatusBadge,
  UpliftIndicator,
  inputCls,
} from "../components/ui"
import { navigate } from "../lib/router"
import { STATUS_META, STATUS_ORDER, num, pct } from "../lib/format"

const columns: Column<ScoredCustomer>[] = [
  {
    key: "id",
    header: "Customer ID",
    width: "120px",
    sortValue: (r) => r.customer_id,
    render: (r) => (
      <span className="font-mono text-[12.5px]">{r.customer_id}</span>
    ),
  },
  {
    key: "pt",
    header: "p_treat",
    align: "right",
    width: "84px",
    sortValue: (r) => r.p_treat,
    render: (r) => <span className="tnum font-mono">{pct(r.p_treat)}</span>,
  },
  {
    key: "pc",
    header: "p_control",
    align: "right",
    width: "84px",
    sortValue: (r) => r.p_control,
    render: (r) => (
      <span className="tnum font-mono text-ink-2">{pct(r.p_control)}</span>
    ),
  },
  {
    key: "bar",
    header: "Control → Treatment",
    width: "22%",
    hideBelow: "lg",
    render: (r) => (
      <ProbabilityDumbbell pTreat={r.p_treat} pControl={r.p_control} />
    ),
  },
  {
    key: "u",
    header: "Uplift",
    align: "right",
    width: "104px",
    sortValue: (r) => r.uplift,
    render: (r) => <UpliftIndicator value={r.uplift} />,
  },
  {
    key: "s",
    header: "Targeting status",
    sortValue: (r) => STATUS_ORDER.indexOf(r.targeting_status),
    render: (r) => <StatusBadge status={r.targeting_status} />,
  },
  {
    key: "r",
    header: "Reason / segment",
    hideBelow: "lg",
    render: (r) => (
      <span className="text-[12.5px] text-ink-2">
        {r.segment}{" "}
        <span className="font-mono text-[11px] text-mute">
          · {r.reason_code}
        </span>
      </span>
    ),
  },
]

export default function Audience() {
  const r = useResource({
    customers: DEMO_CUSTOMERS,
    summary: DEMO_AUDIENCE_SUMMARY,
  })
  const [q, setQ] = useState("")
  const [status, setStatus] = useState<TargetingStatus | "all">("all")
  const [selected, setSelected] = useState<ScoredCustomer | null>(null)

  const filtered = useMemo(() => {
    const list = r.data?.customers ?? []
    return list.filter(
      (c) =>
        (status === "all" || c.targeting_status === status) &&
        c.customer_id.toLowerCase().includes(q.trim().toLowerCase()),
    )
  }, [r.data, q, status])

  return (
    <div className="space-y-6">
      <PageHeader
        step="03"
        title="Audience"
        lede="Every eligible customer as scored by the backend. Read the gap between control and treatment — not the treatment probability alone."
        actions={
          <>
            <IllustrativeTag show={r.illustrative} />
            <Button onClick={() => navigate("/uplift")}>
              Uplift analysis →
            </Button>
          </>
        }
      />

      <Resource
        r={r}
        rows={10}
        empty={
          <Panel>
            <EmptyState title="No customers scored yet">
              Create or score a campaign to populate the audience. Eligible
              customers come from the backend.
            </EmptyState>
          </Panel>
        }
      >
        {({ summary }) => (
          <>
            <Panel className="p-5">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-[13px]">
                  <span className="tnum font-mono font-medium">
                    {num(summary.eligible_customers)}
                  </span>{" "}
                  <span className="text-mute">
                    eligible customers · click a status to filter
                  </span>
                </p>
              </div>
              <Composition
                summary={summary}
                active={status}
                onPick={(s) => setStatus(status === s ? "all" : s)}
              />
            </Panel>

            <Panel>
              <div
                role="search"
                className="flex flex-col gap-3 border-b border-line p-3 md:flex-row md:items-center"
              >
                <label className="relative md:w-64">
                  <span className="sr-only">Search customer ID</span>
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search customer ID…"
                    className={`${inputCls()} h-8 font-mono text-[12.5px]`}
                  />
                </label>
                <label className="flex items-center gap-2 text-[12.5px] text-mute">
                  Status
                  <select
                    value={status}
                    onChange={(e) =>
                      setStatus(e.target.value as TargetingStatus | "all")
                    }
                    className={`${inputCls()} h-8 w-auto text-[12.5px]`}
                  >
                    <option value="all">All statuses</option>
                    {STATUS_ORDER.map((s) => (
                      <option key={s} value={s}>
                        {STATUS_META[s].label}
                      </option>
                    ))}
                  </select>
                </label>
                {(q || status !== "all") && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setQ("")
                      setStatus("all")
                    }}
                  >
                    Clear filters
                  </Button>
                )}
                <div className="md:ml-auto">
                  <DumbbellLegend />
                </div>
              </div>
              {filtered.length === 0 ? (
                <EmptyState title="No customers match these filters">
                  Adjust the search or status filter.
                </EmptyState>
              ) : (
                <DataTable
                  key={`${status}-${q}`}
                  caption="Scored customers"
                  rows={filtered}
                  columns={columns}
                  rowKey={(c) => c.customer_id}
                  selectedKey={selected?.customer_id}
                  onSelect={setSelected}
                  initialSort={{ key: "u", dir: "desc" }}
                  mobileCard={(c) => (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[13px]">
                          {c.customer_id}
                        </span>
                        <UpliftIndicator value={c.uplift} />
                      </div>
                      <ProbabilityDumbbell
                        pTreat={c.p_treat}
                        pControl={c.p_control}
                      />
                      <div className="flex items-center justify-between text-[12px] text-mute">
                        <StatusBadge status={c.targeting_status} short />
                        <span className="tnum font-mono">
                          T {pct(c.p_treat)} · C {pct(c.p_control)}
                        </span>
                      </div>
                    </div>
                  )}
                />
              )}
            </Panel>
          </>
        )}
      </Resource>

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.customer_id ?? ""}
      >
        {selected && (
          <div className="space-y-6 p-5">
            <StatusBadge status={selected.targeting_status} />
            <div className="grid grid-cols-3 gap-3 border-y border-line py-4">
              <div>
                <p className="text-[11.5px] text-mute">Treatment</p>
                <p className="tnum mt-1 font-mono text-[18px]">
                  {pct(selected.p_treat)}
                </p>
              </div>
              <div>
                <p className="text-[11.5px] text-mute">Control</p>
                <p className="tnum mt-1 font-mono text-[18px] text-ink-2">
                  {pct(selected.p_control)}
                </p>
              </div>
              <div>
                <p className="text-[11.5px] text-mute">Uplift</p>
                <p className="mt-1">
                  <UpliftIndicator value={selected.uplift} />
                </p>
              </div>
            </div>
            <div>
              <ProbabilityDumbbell
                pTreat={selected.p_treat}
                pControl={selected.p_control}
                height="lg"
                axis
              />
              <div className="mt-2">
                <DumbbellLegend />
              </div>
            </div>
            <dl className="space-y-2 text-[13px]">
              <div className="flex justify-between">
                <dt className="text-mute">Reason code</dt>
                <dd className="font-mono text-[12px]">
                  {selected.reason_code}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-mute">Segment</dt>
                <dd>{selected.segment}</dd>
              </div>
            </dl>
            <Button
              variant="primary"
              className="w-full"
              onClick={() => navigate(`/explain?id=${selected.customer_id}`)}
            >
              Open full explanation →
            </Button>
          </div>
        )}
      </Drawer>
    </div>
  )
}
