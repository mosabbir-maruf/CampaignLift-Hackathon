import { useEffect, useState } from "react"
import {
  apiClient,
  ApiError,
  type CustomerScoreItem,
  type ScoreRunResponse,
} from "../api/client"
import {
  Badge,
  Button,
  Drawer,
  DumbbellLegend,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricBlock,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  UpliftIndicator,
  inputCls,
} from "../components/ui"
import { Link, navigate, useRoute } from "../lib/router"
import { pct } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"

const PAGE_SIZE = 50

export default function Audience() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id") || query.get("id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [page, setPage] = useState(0)
  const [data, setData] = useState<ScoreRunResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<CustomerScoreItem | null>(null)
  const [q, setQ] = useState("")
  const [nonce, setNonce] = useState(0)

  // Synchronize campaign ID if present in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Reset page when campaign changes
  useEffect(() => {
    setPage(0)
    setQ("")
    setSelected(null)
  }, [activeId])

  // Fetch paginated customer scores from backend inference engine
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
      .scoreCampaign(activeId, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .then((res) => {
        if (!alive) return
        setData(res)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!alive) return
        let msg = "Failed to score campaign."
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
  }, [activeId, page, nonce])

  // Filter within current page by customer ID search term
  const displayedItems = (data?.items ?? []).filter((c) =>
    c.customer_id.toLowerCase().includes(q.trim().toLowerCase()),
  )

  const totalPages = data ? Math.max(1, Math.ceil(data.total_count / PAGE_SIZE)) : 1

  return (
    <div className="space-y-6">
      <PageHeader
        step="03"
        title="Audience"
        lede="Customer-level uplift scores computed directly by the causal inference model. Rank by the difference between treatment and control — not response likelihood alone."
        actions={
          data ? (
            <div className="flex items-center gap-2">
              <Badge tone="neu" dot={false}>
                <span className="font-mono text-[11px]">{data.campaign_id}</span>
              </Badge>
              <Button
                onClick={() =>
                  navigate(
                    activeId
                      ? `/uplift?campaign_id=${encodeURIComponent(activeId)}`
                      : "/uplift",
                  )
                }
              >
                Uplift analysis →
              </Button>
            </div>
          ) : null
        }
      />

      {/* Empty State: No active campaign */}
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
            No active campaign scenario was selected. Define a campaign scenario in
            Campaign Setup before running audience scoring.
          </EmptyState>
        </Panel>
      )}

      {/* Error State: Backend scoring failure */}
      {activeId && error && (
        <Panel className="p-6">
          <ErrorState
            message={error}
            onRetry={() => setNonce((n) => n + 1)}
          />
          <div className="mt-4 flex items-center gap-3 border-t border-line pt-4 text-[12.5px]">
            <Link to="/setup" className="font-medium text-primary hover:underline">
              ← Return to Campaign Setup
            </Link>
            <span className="text-mute">·</span>
            <Link to="/" className="font-medium text-primary hover:underline">
              Open Overview
            </Link>
          </div>
        </Panel>
      )}

      {/* Loading State: Model inference running */}
      {activeId && loading && (
        <Panel className="p-6">
          <LoadingState
            rows={10}
            label="Executing backend causal inference and scoring eligible customers"
          />
        </Panel>
      )}

      {/* Ready State: Scored customer population */}
      {activeId && !loading && !error && data && (
        <>
          {/* Summary Panel */}
          <Panel className="p-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <MetricBlock
                label="Total Scored Population"
                value={data.total_scored.toLocaleString()}
                note={`of ${data.total_count.toLocaleString()} in dataset`}
              />
              <MetricBlock
                label="Eligible Customers"
                value={data.total_eligible.toLocaleString()}
                note="Meets eligibility criteria"
              />
              <MetricBlock
                label="Model Version"
                value={<span className="font-mono text-[14px]">{data.model_version}</span>}
                note={`Dataset: ${data.dataset_version}`}
              />
              <MetricBlock
                label="Batch Run ID"
                value={<span className="font-mono text-[12px]">{data.run_id}</span>}
                note={`Limit: ${data.limit} · Offset: ${data.offset}`}
              />
            </div>
          </Panel>

          {/* Scored Customers Table Panel */}
          <Panel>
            {/* Search and Legend Toolbar */}
            <div
              role="search"
              className="flex flex-col gap-3 border-b border-line p-3 md:flex-row md:items-center"
            >
              <label className="relative md:w-72">
                <span className="sr-only">Search customer ID on current page</span>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Filter customer ID on page…"
                  className={`${inputCls()} h-8 font-mono text-[12.5px]`}
                />
              </label>
              {q && (
                <Button variant="ghost" onClick={() => setQ("")}>
                  Clear search
                </Button>
              )}
              <div className="text-[12px] text-mute md:ml-2">
                Showing {displayedItems.length} of {data.items.length} items on page
              </div>
              <div className="md:ml-auto">
                <DumbbellLegend />
              </div>
            </div>

            {/* Table */}
            {displayedItems.length === 0 ? (
              <div className="p-6">
                <EmptyState title="No customers match this filter">
                  {q
                    ? `No customers on the current page match "${q}". Clear the search to view all results.`
                    : "No customers were returned in this scoring page."}
                </EmptyState>
              </div>
            ) : (
              <div className="scroll-quiet max-h-[640px] overflow-auto">
                <table className="w-full border-collapse text-[13px]">
                  <caption className="sr-only">
                    Scored customers for campaign {data.campaign_id}
                  </caption>
                  <thead className="sticky top-0 z-10 bg-surface">
                    <tr className="border-b border-line-strong text-[11.5px] font-medium text-mute">
                      <th scope="col" className="h-9 px-3 text-left">
                        Customer ID
                      </th>
                      <th scope="col" className="h-9 px-3 text-right">
                        p_treat
                      </th>
                      <th scope="col" className="h-9 px-3 text-right">
                        p_control
                      </th>
                      <th scope="col" className="h-9 px-3 text-left w-[24%]">
                        Control → Treatment
                      </th>
                      <th scope="col" className="h-9 px-3 text-right">
                        Uplift
                      </th>
                      <th scope="col" className="h-9 px-3 text-right">
                        Uplift Rank
                      </th>
                      <th scope="col" className="h-9 px-3 text-right">
                        Response Rank
                      </th>
                      <th scope="col" className="h-9 px-3 text-center">
                        Eligibility
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedItems.map((c) => {
                      const isSelected = selected?.customer_id === c.customer_id
                      return (
                        <tr
                          key={c.customer_id}
                          onClick={() => setSelected(c)}
                          className={`cursor-pointer border-b border-line/70 transition-colors hover:bg-paper ${
                            isSelected ? "bg-primary-soft/40" : ""
                          }`}
                        >
                          <td className="px-3 py-2.5 font-mono text-[12.5px] font-medium text-ink">
                            {c.customer_id}
                          </td>
                          <td className="tnum px-3 py-2.5 text-right font-mono text-[13px]">
                            {pct(c.p_treat)}
                          </td>
                          <td className="tnum px-3 py-2.5 text-right font-mono text-[13px] text-ink-2">
                            {pct(c.p_control)}
                          </td>
                          <td className="px-3 py-2.5">
                            <ProbabilityDumbbell
                              pTreat={c.p_treat}
                              pControl={c.p_control}
                            />
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <UpliftIndicator value={c.uplift} />
                          </td>
                          <td className="tnum px-3 py-2.5 text-right font-mono text-[12px] text-ink">
                            #{c.uplift_rank}
                          </td>
                          <td className="tnum px-3 py-2.5 text-right font-mono text-[12px] text-mute">
                            #{c.response_rank}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <Badge tone={c.eligible ? "pos" : "neu"}>
                              {c.eligible ? "Eligible" : "Ineligible"}
                            </Badge>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Server Pagination Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-[12.5px]">
              <div className="text-mute">
                Showing customers{" "}
                <span className="font-mono font-medium text-ink">
                  {data.offset + 1}
                </span>{" "}
                –{" "}
                <span className="font-mono font-medium text-ink">
                  {Math.min(data.offset + data.limit, data.total_count)}
                </span>{" "}
                of{" "}
                <span className="font-mono font-medium text-ink">
                  {data.total_count.toLocaleString()}
                </span>{" "}
                scored
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  disabled={page === 0 || loading}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  ← Previous
                </Button>
                <span className="px-2 font-mono text-[12px] text-mute">
                  Page {page + 1} of {totalPages}
                </span>
                <Button
                  variant="ghost"
                  disabled={(page + 1) * PAGE_SIZE >= data.total_count || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next →
                </Button>
              </div>
            </div>
          </Panel>
        </>
      )}

      {/* Customer Explanation Drawer */}
      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `Customer ${selected.customer_id}` : ""}
      >
        {selected && (
          <div className="space-y-6 p-5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[14px] font-semibold text-ink">
                {selected.customer_id}
              </span>
              <Badge tone={selected.eligible ? "pos" : "neu"}>
                {selected.eligible ? "Eligible" : "Ineligible"}
              </Badge>
            </div>

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

            <dl className="divide-y divide-line/70 text-[13px]">
              <div className="flex justify-between py-2">
                <dt className="text-mute">Uplift rank</dt>
                <dd className="font-mono text-[12px] font-medium text-ink">
                  #{selected.uplift_rank}
                </dd>
              </div>
              <div className="flex justify-between py-2">
                <dt className="text-mute">Response rank</dt>
                <dd className="font-mono text-[12px] text-ink">
                  #{selected.response_rank}
                </dd>
              </div>
              <div className="flex justify-between py-2">
                <dt className="text-mute">Eligible</dt>
                <dd className="text-ink">
                  {selected.eligible ? "Yes" : "No"}
                </dd>
              </div>
            </dl>

            {activeId && (
              <Button
                variant="primary"
                className="w-full"
                onClick={() =>
                  navigate(
                    `/explain?id=${encodeURIComponent(selected.customer_id)}&campaign_id=${encodeURIComponent(activeId)}`,
                  )
                }
              >
                Open full explanation →
              </Button>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
