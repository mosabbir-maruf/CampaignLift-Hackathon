import { useEffect, useState } from "react"
import {
  apiClient,
  ApiError,
  type CustomerExplanationResponse,
  type ExplanationReasonCode,
} from "../api/client"
import {
  Badge,
  Button,
  DumbbellLegend,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  ProbabilityDumbbell,
  SectionHeader,
  UpliftIndicator,
  inputCls,
} from "../components/ui"
import { navigate, useRoute } from "../lib/router"
import { pct, pp, type Tone } from "../lib/format"
import { getActiveCampaignId, setActiveCampaignId } from "../lib/campaign"

const REASON_CONFIG: Record<ExplanationReasonCode, {
  label: string
  tone: Tone
  badgeTone: Tone
  summary: string
}> = {
  incremental_candidate: {
    label: "Incremental Candidate",
    tone: "pos",
    badgeTone: "pos",
    summary:
      "Predicted positive uplift. The incentive is expected to create incremental response for this customer.",
  },
  likely_without_offer: {
    label: "Likely Without Offer",
    tone: "warn",
    badgeTone: "warn",
    summary:
      "High baseline conversion probability. Customer is expected to convert regardless; offer may be redundant spend.",
  },
  negative_uplift: {
    label: "Potential Negative Uplift",
    tone: "neg",
    badgeTone: "neg",
    summary:
      "Negative uplift predicted (sleeping dog). The offer is associated with reduced response or negative reaction.",
  },
  weak_response: {
    label: "Weak Response",
    tone: "neu",
    badgeTone: "neu",
    summary:
      "Low response probabilities under both treatment and control. Minimal responsiveness expected.",
  },
}

interface ContributionChartItem {
  name: string
  value: string
  contribution: number
}

function ContributionChart({ items }: { items: ContributionChartItem[] }) {
  if (!items || items.length === 0) {
    return (
      <p className="text-[12.5px] text-mute py-4">
        No feature contribution breakdown available for this customer.
      </p>
    )
  }

  const max = Math.max(...items.map((i) => Math.abs(i.contribution)), 0.001)

  return (
    <ul className="space-y-3" aria-label="Feature contributions">
      {items.map((i) => {
        const w = (Math.abs(i.contribution) / max) * 48
        const pos = i.contribution >= 0
        return (
          <li
            key={i.name}
            className="grid grid-cols-[1fr] gap-1 md:grid-cols-[minmax(0,180px)_1fr_75px] md:items-center md:gap-3"
          >
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-ink">
                {i.name}
              </p>
              <p className="tnum font-mono text-[11.5px] text-mute truncate">
                {i.value}
              </p>
            </div>
            <div
              className="relative h-4 bg-sunken rounded-xs overflow-hidden"
              role="img"
              aria-label={`${i.name}: ${pp(i.contribution)} ${
                pos ? "toward" : "against"
              } uplift`}
            >
              <div className="absolute inset-y-0 left-1/2 w-px bg-line-strong z-10" />
              <div
                className={`absolute inset-y-0.5 rounded-xs transition-all duration-300 ${
                  pos ? "bg-pos" : "bg-neg"
                }`}
                style={
                  pos
                    ? { left: "50%", width: `${w}%` }
                    : { right: "50%", width: `${w}%` }
                }
              />
            </div>
            <p
              className={`tnum text-right font-mono text-[12px] font-semibold ${
                pos ? "text-pos" : "text-neg"
              }`}
            >
              {pp(i.contribution)}
            </p>
          </li>
        )
      })}
      <li className="flex justify-between border-t border-line/60 pt-2 text-[11px] text-mute">
        <span>← Lowers estimated uplift</span>
        <Badge tone="neu" dot={false}>
          Model contributions (not causal causes)
        </Badge>
        <span>Raises estimated uplift →</span>
      </li>
    </ul>
  )
}

export default function CustomerExplanation() {
  const { query } = useRoute()
  const urlCampaignId = query.get("campaign_id")
  const activeCampaignId = urlCampaignId || getActiveCampaignId()
  const customerIdParam = (
    query.get("id") ||
    query.get("customer_id") ||
    ""
  ).trim()

  const [lookup, setLookup] = useState(customerIdParam)
  const [data, setData] = useState<CustomerExplanationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [nonce, setNonce] = useState(0)

  // Synchronize campaign ID if present in URL
  useEffect(() => {
    if (urlCampaignId) {
      setActiveCampaignId(urlCampaignId)
    }
  }, [urlCampaignId])

  // Synchronize input with URL query param
  useEffect(() => {
    setLookup(customerIdParam)
  }, [customerIdParam])

  // Fetch customer explanation from backend API
  useEffect(() => {
    if (!activeCampaignId || !customerIdParam) {
      setData(null)
      setLoading(false)
      setError(null)
      setNotFound(false)
      return
    }

    let alive = true
    setLoading(true)
    setError(null)
    setNotFound(false)

    apiClient
      .getCustomerExplanation(activeCampaignId, customerIdParam)
      .then((res) => {
        if (!alive) return
        setData(res)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!alive) return
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true)
          setLoading(false)
          return
        }
        let msg = "Failed to load customer explanation."
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
  }, [activeCampaignId, customerIdParam, nonce])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = lookup.trim()
    if (!trimmed) return
    const qs = new URLSearchParams()
    qs.set("id", trimmed)
    if (activeCampaignId) {
      qs.set("campaign_id", activeCampaignId)
    }
    navigate(`/explain?${qs.toString()}`)
  }

  const reasonMeta = data ? REASON_CONFIG[data.reason_code] : null

  return (
    <div className="space-y-6">
      <PageHeader
        step="07"
        title="Customer Explanation"
        lede="Why the model suggests a decision for an individual customer. Feature contributions reflect statistical associations in the model — not proven causal drivers."
        actions={
          <form className="flex gap-2" onSubmit={handleSearch}>
            <label className="sr-only" htmlFor="cid">
              Customer ID
            </label>
            <input
              id="cid"
              value={lookup}
              onChange={(e) => setLookup(e.target.value)}
              placeholder="e.g. CUS-10001"
              className={`${inputCls()} h-8 w-44 font-mono text-[12.5px]`}
            />
            <Button type="submit" disabled={!lookup.trim()}>
              Load
            </Button>
          </form>
        }
      />

      {!activeCampaignId && (
        <Panel>
          <EmptyState
            title="No active campaign"
            action={
              <Button variant="primary" onClick={() => navigate("/setup")}>
                Go to Campaign Setup
              </Button>
            }
          >
            Select or configure a campaign first to inspect customer-level
            explanations.
          </EmptyState>
        </Panel>
      )}

      {activeCampaignId && !customerIdParam && (
        <Panel>
          <EmptyState
            title="No customer selected"
            action={
              <Button
                variant="primary"
                onClick={() =>
                  navigate(
                    urlCampaignId
                      ? `/audience?campaign_id=${encodeURIComponent(activeCampaignId)}`
                      : "/audience",
                  )
                }
              >
                Go to Audience
              </Button>
            }
          >
            Enter a Customer ID above or select any customer from the Audience
            table to inspect their model predictions and feature contributions.
          </EmptyState>
        </Panel>
      )}

      {activeCampaignId && customerIdParam && loading && (
        <Panel>
          <LoadingState
            rows={8}
            label={`Loading explanation for customer ${customerIdParam}`}
          />
        </Panel>
      )}

      {activeCampaignId && customerIdParam && !loading && notFound && (
        <Panel>
          <EmptyState
            title={`Customer "${customerIdParam}" not found`}
            action={
              <Button
                variant="primary"
                onClick={() =>
                  navigate(
                    urlCampaignId
                      ? `/audience?campaign_id=${encodeURIComponent(activeCampaignId)}`
                      : "/audience",
                  )
                }
              >
                Pick from Audience
              </Button>
            }
          >
            Customer &ldquo;{customerIdParam}&rdquo; was not found in the scored
            population for campaign &ldquo;{activeCampaignId}&rdquo;. Verify the
            identifier or select an eligible customer from the Audience screen.
          </EmptyState>
        </Panel>
      )}

      {activeCampaignId &&
        customerIdParam &&
        !loading &&
        !notFound &&
        error && (
          <Panel>
            <ErrorState
              message={error}
              onRetry={() => setNonce((n) => n + 1)}
            />
          </Panel>
        )}

      {activeCampaignId &&
        customerIdParam &&
        !loading &&
        !notFound &&
        !error &&
        data && (
          <div className="grid gap-6 lg:grid-cols-[1fr_1.25fr]">
            <Panel>
              <div className="border-b border-line p-5">
                <p className="font-mono text-[12px] text-mute">
                  {data.customer_id}
                </p>
                <p className="mt-3 text-[11.5px] font-medium text-mute uppercase tracking-wider">
                  Backend Reason Code
                </p>
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className={`text-[20px] font-semibold tracking-tight ${
                      reasonMeta ? `text-${reasonMeta.tone}` : "text-ink"
                    }`}
                  >
                    {reasonMeta?.label || data.reason_code}
                  </span>
                  <Badge tone={reasonMeta?.badgeTone || "neu"} dot={false}>
                    {data.reason_code}
                  </Badge>
                </div>
                <p className="mt-2 text-[12.5px] text-ink-2 leading-relaxed">
                  {reasonMeta?.summary}
                </p>
              </div>

              <div className="space-y-4 p-5">
                <dl className="grid grid-cols-3 gap-3">
                  <div>
                    <dt className="text-[11.5px] text-mute">
                      Treatment (p_treat)
                    </dt>
                    <dd className="tnum mt-1 font-mono text-[19px] font-semibold">
                      {pct(data.p_treat)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] text-mute">
                      Control (p_control)
                    </dt>
                    <dd className="tnum mt-1 font-mono text-[19px] text-ink-2">
                      {pct(data.p_control)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11.5px] text-mute">
                      Predicted Uplift
                    </dt>
                    <dd className="mt-1">
                      <UpliftIndicator value={data.uplift} size="lg" />
                    </dd>
                  </div>
                </dl>
                <ProbabilityDumbbell
                  pTreat={data.p_treat}
                  pControl={data.p_control}
                  height="lg"
                  axis
                />
                <DumbbellLegend />
              </div>

              <div className="border-t border-line p-5 bg-paper/50">
                <p className="text-[11.5px] font-medium text-mute uppercase tracking-wider">
                  Grounded Explanation Text
                </p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink font-sans">
                  {data.template_text}
                </p>
              </div>
            </Panel>

            <div className="space-y-6">
              <Panel className="p-5">
                <SectionHeader
                  title="Top Feature Contributions"
                  meta="Signed SHAP / model attribution"
                />
                <ContributionChart items={data.feature_contributions} />
              </Panel>

              <aside className="rounded-[5px] border border-line bg-paper p-4 text-[12.5px] leading-relaxed text-ink-2">
                <p className="font-semibold text-ink">
                  Important Note on Causal Claims
                </p>
                <ul className="mt-1.5 list-disc space-y-1.5 pl-4">
                  <li>
                    <strong>Contributions are signals, not causes:</strong>{" "}
                    Feature contributions describe mathematical weights applied
                    by the model, not proven real-world causes of customer
                    behavior.
                  </li>
                  <li>
                    <strong>Estimates carry uncertainty:</strong> Predicted
                    probabilities are statistical outputs from machine learning
                    models trained on synthetic data.
                  </li>
                  <li>
                    <strong>Review before acting:</strong> If a recommendation
                    appears inconsistent with domain knowledge, verify the
                    customer profile in the Audience screen rather than assuming
                    ground truth.
                  </li>
                </ul>
              </aside>
            </div>
          </div>
        )}
    </div>
  )
}
