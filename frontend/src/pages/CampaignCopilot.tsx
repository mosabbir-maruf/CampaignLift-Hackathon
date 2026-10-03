import { useEffect, useRef, useState } from "react"
import {
  apiClient,
  ApiError,
  type CampaignResponse,
  type CopilotResponse,
} from "../api/client"
import {
  Button,
  EmptyState,
  PageHeader,
  Panel,
  SectionHeader,
  inputCls,
} from "../components/ui"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"
import { navigate, useRoute } from "../lib/router"

type Turn = {
  q: string
  a: CopilotResponse | null
  error?: string | null
}

const SUGGESTIONS = [
  "How does uplift targeting compare against random baseline spend?",
  "Why were customers with negative uplift excluded from the budget?",
  "What is the observed incremental response rate from the trial?",
  "Which features contributed most to predicted uplift?",
]

export default function CampaignCopilot() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id")
  const activeId = urlCampaignId || getActiveCampaignId()

  const [campaign, setCampaign] = useState<CampaignResponse | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [runLoading, setRunLoading] = useState(false)
  const [serviceUnavailable, setServiceUnavailable] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState("")
  const endRef = useRef<HTMLDivElement>(null)

  const busy = turns.some((t) => !t.a && !t.error)

  // Synchronize campaign ID if present in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Scroll to latest message
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  }, [turns])

  // Fetch campaign definition and active run_id on mount or activeId change
  useEffect(() => {
    if (!activeId) {
      setCampaign(null)
      setRunId(null)
      setTurns([])
      return
    }

    let alive = true
    setRunLoading(true)

    // Fetch campaign
    apiClient
      .getCampaign(activeId)
      .then((c) => {
        if (!alive) return
        setCampaign(c)
      })
      .catch(() => {})

    // Fetch run_id via scoreCampaign (limit: 1) or getStrategyComparison
    apiClient
      .scoreCampaign(activeId, { limit: 1 })
      .then((res) => {
        if (!alive) return
        setRunId(res.run_id)
        setRunLoading(false)
      })
      .catch((err: unknown) => {
        if (!alive) return
        if (err instanceof ApiError && err.status === 503) {
          // Model/data not ready
        }
        setRunLoading(false)
      })

    return () => {
      alive = false
    }
  }, [activeId])

  const ask = async (q: string) => {
    const question = q.trim()
    if (!question || busy || !activeId) return
    setInput("")

    if (!runId) {
      setTurns((prev) => [
        ...prev,
        {
          q: question,
          a: null,
          error:
            "No verified run ID available. Score the campaign in Audience or run Budget Optimization first so Copilot can ground answers.",
        },
      ])
      return
    }

    setTurns((prev) => [...prev, { q: question, a: null }])

    try {
      const res = await apiClient.queryCopilot(activeId, {
        question,
        run_id: runId,
      })

      if (res.unavailable) {
        setServiceUnavailable(true)
      }

      setTurns((prev) =>
        prev.map((t, idx) => (idx === prev.length - 1 ? { ...t, a: res } : t)),
      )
    } catch (err: unknown) {
      let errMsg = "Copilot query failed."
      if (err instanceof ApiError) {
        if (err.status === 503) {
          setServiceUnavailable(true)
        }
        errMsg = err.errorResponse?.message || err.message
        if (err.errorResponse?.detail) {
          errMsg += ` (${err.errorResponse.detail})`
        }
      } else if (err instanceof Error) {
        errMsg = err.message
      }

      setTurns((prev) =>
        prev.map((t, idx) =>
          idx === prev.length - 1 ? { ...t, a: null, error: errMsg } : t,
        ),
      )
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        step="09"
        title="Campaign Copilot"
        lede="Inquire about campaign strategy, uplift scores, and optimization outputs. Answers are strictly grounded in verified SQLite run context and disclose all fields referenced."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <Panel className="flex min-h-[540px] flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3 text-[12px]">
            <span className="text-mute">
              Grounded in:{" "}
              <span className="font-mono font-medium text-ink">
                {activeId || "No campaign selected"}
              </span>
              {campaign && <span> · {campaign.name}</span>}
              {runId && (
                <span className="font-mono text-mute text-[11px]">
                  {" "}
                  · {runId}
                </span>
              )}
            </span>
            <span
              className={`flex items-center gap-1.5 ${
                serviceUnavailable ? "text-neg" : "text-pos"
              }`}
            >
              <span
                className={`size-2 rounded-full ${
                  serviceUnavailable ? "bg-neg" : "bg-pos"
                }`}
              />
              {serviceUnavailable ? "Unavailable (503)" : "Ready"}
            </span>
          </div>

          <div
            className="scroll-quiet flex-1 space-y-6 overflow-y-auto p-5"
            aria-live="polite"
          >
            {!activeId && (
              <EmptyState
                title="No active campaign"
                action={
                  <Button variant="primary" onClick={() => navigate("/setup")}>
                    Go to Campaign Setup
                  </Button>
                }
              >
                Select or configure a campaign first to use Campaign Copilot.
              </EmptyState>
            )}

            {activeId && !runId && !runLoading && (
              <div className="border-l-2 border-warn bg-warn-soft/40 p-4">
                <p className="text-[13px] font-semibold text-warn">
                  Run context not yet scored
                </p>
                <p className="mt-1 text-[12.5px] text-ink-2">
                  This campaign has not been scored yet. Copilot requires a
                  verified score run to ground its responses. Visit{" "}
                  <button
                    onClick={() =>
                      navigate(
                        urlCampaignId
                          ? `/audience?campaign_id=${encodeURIComponent(activeId)}`
                          : "/audience",
                      )
                    }
                    className="font-medium text-primary underline"
                  >
                    Audience
                  </button>{" "}
                  or{" "}
                  <button
                    onClick={() =>
                      navigate(
                        urlCampaignId
                          ? `/budget?campaign_id=${encodeURIComponent(activeId)}`
                          : "/budget",
                      )
                    }
                    className="font-medium text-primary underline"
                  >
                    Budget Optimization
                  </button>{" "}
                  first.
                </p>
              </div>
            )}

            {serviceUnavailable && (
              <div className="border-l-2 border-neg bg-neg-soft/40 p-4">
                <p className="text-[13px] font-semibold text-neg">
                  Copilot Service Unavailable
                </p>
                <p className="mt-1 max-w-lg text-[12.5px] text-ink-2">
                  The backend Gemini Copilot service is disabled (GEMINI_API_KEY
                  is not configured) or currently unreachable. The rest of
                  CampaignLift is completely unaffected — all audience, uplift,
                  budget, and experiment views operate independently.
                </p>
              </div>
            )}

            {turns.length === 0 && activeId && runId && !serviceUnavailable && (
              <div className="max-w-lg">
                <p className="text-[14px] font-semibold text-ink">
                  Ask a grounded question about this campaign.
                </p>
                <p className="mt-1 text-[13px] text-mute leading-relaxed">
                  Copilot answers strictly using verified run JSON context
                  (scoring, optimization, and experiment outputs). If context is
                  insufficient, it will state so rather than hallucinating.
                </p>
              </div>
            )}

            {turns.map((t, i) => (
              <article key={i} className="space-y-3">
                <p className="ml-auto w-fit max-w-[85%] rounded-[4px] bg-ink px-3.5 py-2 text-[13px] text-white">
                  {t.q}
                </p>

                {t.a ? (
                  <div className="max-w-[92%] border-l-2 border-primary pl-4 py-1">
                    <p className="text-[13.5px] leading-relaxed text-ink whitespace-pre-wrap">
                      {t.a.answer}
                    </p>
                    {t.a.context_fields_used &&
                      t.a.context_fields_used.length > 0 && (
                        <div className="mt-3">
                          <p className="font-mono text-[10.5px] tracking-wider text-mute uppercase">
                            Context fields used for grounding
                          </p>
                          <ul className="mt-1.5 flex flex-wrap gap-1.5">
                            {t.a.context_fields_used.map((f) => (
                              <li
                                key={f}
                                className="rounded-[3px] bg-sunken px-1.5 py-0.5 font-mono text-[11px] text-ink-2"
                              >
                                {f}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                ) : t.error ? (
                  <div className="max-w-[92%] border-l-2 border-neg pl-4 py-1 bg-neg-soft/30 p-3 rounded-r-xs">
                    <p className="text-[12.5px] font-medium text-neg">
                      Unable to complete Copilot inquiry
                    </p>
                    <p className="mt-1 text-[12px] text-ink-2">{t.error}</p>
                  </div>
                ) : (
                  <p className="animate-pulse-soft pl-4 text-[12.5px] text-mute">
                    Grounding inquiry against verified run context…
                  </p>
                )}
              </article>
            ))}

            <div ref={endRef} />
          </div>

          <form
            className="flex gap-2 border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault()
              ask(input)
            }}
          >
            <label htmlFor="q" className="sr-only">
              Ask a question
            </label>
            <input
              id="q"
              value={input}
              disabled={serviceUnavailable || !activeId}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                serviceUnavailable
                  ? "Copilot service is currently unavailable"
                  : !activeId
                    ? "Select a campaign to begin"
                    : "Ask about audience uplift, budget allocations, or experiment results…"
              }
              className={`${inputCls()} h-9 flex-1 text-[13.5px] disabled:bg-sunken`}
            />
            <Button
              type="submit"
              variant="primary"
              className="h-9"
              disabled={
                serviceUnavailable || busy || !input.trim() || !activeId
              }
            >
              Ask
            </Button>
          </form>
        </Panel>

        <aside className="space-y-6">
          <Panel className="p-4">
            <SectionHeader title="Suggested questions" />
            <ul className="space-y-1">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button
                    disabled={serviceUnavailable || busy || !activeId}
                    onClick={() => ask(s)}
                    className="w-full rounded-[3px] px-2 py-1.5 text-left text-[12.5px] text-ink-2 hover:bg-paper hover:text-ink disabled:opacity-40 transition-colors"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          <div className="px-1 text-[12px] leading-relaxed text-mute">
            Copilot requests are proxied securely through the backend. No API
            keys or LLM credentials exist in the browser. Answers reflect only
            run output data.
          </div>
        </aside>
      </div>
    </div>
  )
}
