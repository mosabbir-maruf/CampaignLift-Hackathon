import { useState } from "react"
import {
  apiClient,
  ApiError,
  type CampaignCreateRequest,
  type CampaignResponse,
  type CampaignObjective,
  type CampaignOfferType,
  type CampaignChannel,
} from "../api/client"
import {
  Button,
  FormField,
  PageHeader,
  Panel,
  SectionHeader,
  inputCls,
  Badge,
  SelectDropdown,
} from "../components/ui"
import { Link, navigate } from "../lib/router"
import { bdt } from "../lib/format"
import { setActiveCampaignId } from "../lib/campaign"

type Errors = Partial<Record<keyof CampaignCreateRequest, string>>
type Phase = "idle" | "saving" | "success" | "error"

const OBJECTIVES: {
  value: CampaignObjective
  label: string
  desc: string
}[] = [
  {
    value: "reactivation",
    label: "Dormant Reactivation",
    desc: "Re-engage dormant wallet users who have not transacted recently.",
  },
  {
    value: "activation",
    label: "User Activation",
    desc: "Drive first-time transactions among newly onboarded users.",
  },
  {
    value: "qr_adoption",
    label: "Merchant QR Adoption",
    desc: "Accelerate merchant QR payments and merchant acceptance.",
  },
  {
    value: "retention",
    label: "Churn Retention",
    desc: "Retain high-value customers exhibiting churn risk indicators.",
  },
]

const OFFER_TYPES: {
  value: CampaignOfferType
  label: string
  unitHint: string
}[] = [
  {
    value: "flat_cashback",
    label: "Flat Cashback (৳)",
    unitHint: "Cashback amount in BDT per qualifying transaction.",
  },
  {
    value: "pct_cashback",
    label: "Percentage Cashback (%)",
    unitHint: "Percentage of transaction value granted as incentive.",
  },
  {
    value: "fee_waiver",
    label: "Fee Waiver",
    unitHint: "Full or partial transaction fee waiver (value is 0).",
  },
]

const OFFER_TYPE_OPTIONS = OFFER_TYPES.map((o) => ({
  value: o.value,
  label: o.label,
}))

const CHANNELS: {
  value: CampaignChannel
  label: string
  desc: string
}[] = [
  {
    value: "push",
    label: "Push Notification",
    desc: "Direct push message with in-app routing.",
  },
  {
    value: "sms",
    label: "SMS",
    desc: "Direct telco SMS text message for wide reach.",
  },
  {
    value: "in_app",
    label: "In-App Banner",
    desc: "Targeted card banner within wallet transaction flow.",
  },
]

const INITIAL_FORM: CampaignCreateRequest = {
  name: "",
  objective: "reactivation",
  offer_type: "flat_cashback",
  incentive_value: 50,
  incentive_cost_bdt: 50,
  budget_bdt: 500000,
  channel: "push",
}

function validate(req: CampaignCreateRequest): Errors {
  const e: Errors = {}
  if (!req.name.trim()) {
    e.name = "Campaign name is required."
  } else if (req.name.length > 255) {
    e.name = "Campaign name cannot exceed 255 characters."
  }
  if (!req.objective) {
    e.objective = "Select a campaign objective."
  }
  if (!req.offer_type) {
    e.offer_type = "Select an offer type."
  }
  if (req.incentive_value < 0) {
    e.incentive_value = "Incentive value cannot be negative."
  }
  if (req.offer_type === "flat_cashback" && req.incentive_value <= 0) {
    e.incentive_value = "Flat cashback value must be greater than 0."
  }
  if (req.incentive_cost_bdt < 0) {
    e.incentive_cost_bdt = "Unit incentive cost cannot be negative."
  }
  if (req.budget_bdt <= 0) {
    e.budget_bdt = "Total budget must be greater than 0 BDT."
  } else if (
    req.incentive_cost_bdt > 0 &&
    req.budget_bdt < req.incentive_cost_bdt
  ) {
    e.budget_bdt = "Budget cannot be smaller than the unit incentive cost."
  }
  if (!req.channel) {
    e.channel = "Select a delivery channel."
  }
  return e
}

export default function CampaignSetup() {
  const [form, setForm] = useState<CampaignCreateRequest>(INITIAL_FORM)
  const [errors, setErrors] = useState<Errors>({})
  const [phase, setPhase] = useState<Phase>("idle")
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [createdCampaign, setCreatedCampaign] =
    useState<CampaignResponse | null>(null)

  const setField = <K extends keyof CampaignCreateRequest,>(
    key: K,
    val: CampaignCreateRequest[K],
  ) => {
    setForm((prev) => {
      const next = { ...prev, [key]: val }
      // Auto-sync incentive cost for flat cashback when incentive value changes
      if (
        key === "incentive_value" &&
        prev.offer_type === "flat_cashback" &&
        typeof val === "number"
      ) {
        next.incentive_cost_bdt = val
      }
      if (key === "offer_type") {
        if (val === "fee_waiver") {
          next.incentive_value = 0
        } else if (val === "flat_cashback") {
          next.incentive_cost_bdt = next.incentive_value || 50
        }
      }
      return next
    })
    if (errors[key]) {
      setErrors((prev) => ({ ...prev, [key]: undefined }))
    }
    if (phase !== "idle" && phase !== "saving") {
      setPhase("idle")
      setGeneralError(null)
    }
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setGeneralError(null)
    const clientErrors = validate(form)
    setErrors(clientErrors)

    if (Object.keys(clientErrors).length > 0) {
      const firstField = Object.keys(clientErrors)[0]
      document.getElementById(firstField)?.focus()
      return
    }

    setPhase("saving")
    try {
      // POST the exact typed CampaignCreateRequest payload to the backend
      const res = await apiClient.createCampaign(form)
      setCreatedCampaign(res)
      setActiveCampaignId(res.id)
      setPhase("success")
    } catch (err: unknown) {
      setPhase("error")
      if (err instanceof ApiError) {
        const errorResp = err.errorResponse
        const message = errorResp?.message || err.message
        const detail = errorResp?.detail
        setGeneralError(detail ? `${message}: ${detail}` : message)

        // Parse field-level errors if backend detail contains field names
        if (detail) {
          const fieldErrors: Errors = {}
          const fields: Array<keyof CampaignCreateRequest> = [
            "name",
            "objective",
            "offer_type",
            "incentive_value",
            "incentive_cost_bdt",
            "budget_bdt",
            "channel",
          ]
          for (const f of fields) {
            if (detail.toLowerCase().includes(f.toLowerCase())) {
              fieldErrors[f] = detail
            }
          }
          if (Object.keys(fieldErrors).length > 0) {
            setErrors((prev) => ({ ...prev, ...fieldErrors }))
          }
        }
      } else if (err instanceof Error) {
        setGeneralError(err.message)
      } else {
        setGeneralError(
          "An unexpected error occurred while communicating with the backend API.",
        )
      }
    }
  }

  const handleReset = () => {
    setForm(INITIAL_FORM)
    setErrors({})
    setPhase("idle")
    setGeneralError(null)
    setCreatedCampaign(null)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        step="02"
        title="Campaign Setup"
        lede="Define the campaign scenario and incentive budget. Eligible populations are evaluated by backend inference on the active dataset version — customer list uploads are not required or accepted."
        actions={
          createdCampaign ? (
            <Badge tone="pos" dot={false}>
              <span className="font-mono">{createdCampaign.id}</span>
            </Badge>
          ) : undefined
        }
      />

      <form
        onSubmit={submit}
        noValidate
        className="grid gap-6 lg:grid-cols-[1fr_340px]"
      >
        <div className="space-y-6">
          {/* General Error State */}
          {phase === "error" && (
            <div
              role="alert"
              className="border-l-2 border-neg bg-neg-soft p-4 text-[13px] text-neg"
            >
              <p className="font-semibold text-neg">Campaign Creation Failed</p>
              <p className="mt-1 text-ink-2">
                {generalError ||
                  "The backend rejected the request. Please verify connection to the API service."}
              </p>
              <p className="mt-2 text-[12px] text-mute">
                Form inputs are preserved. Correct any highlighted fields and
                resubmit.
              </p>
            </div>
          )}

          {/* Success State */}
          {phase === "success" && createdCampaign && (
            <div
              role="status"
              className="border-l-2 border-pos bg-pos-soft p-5 text-[13px]"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[15px] font-semibold text-pos">
                  Campaign Created Successfully
                </p>
                <Badge tone="pos">Saved in Backend</Badge>
              </div>
              <p className="mt-1.5 text-ink-2">
                Identifier:{" "}
                <span className="font-mono font-semibold text-ink">
                  {createdCampaign.id}
                </span>
                . The campaign scenario is stored and available for audience
                scoring.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  variant="primary"
                  onClick={() =>
                    navigate(`/?campaign_id=${createdCampaign.id}`)
                  }
                >
                  View in Overview →
                </Button>
                <Button
                  type="button"
                  onClick={() =>
                    navigate(`/audience?campaign_id=${createdCampaign.id}`)
                  }
                >
                  Proceed to Audience Scoring →
                </Button>
                <Button type="button" onClick={handleReset}>
                  Create Another
                </Button>
              </div>
            </div>
          )}

          {/* Panel 1: Campaign Identity */}
          <Panel className="p-5">
            <SectionHeader title="Campaign Identity" />
            <div className="space-y-4">
              <FormField
                id="name"
                label="Campaign name"
                required
                error={errors.name}
                hint="Descriptive name shown across reports and decision views (max 255 characters)."
              >
                <input
                  id="name"
                  className={inputCls(!!errors.name)}
                  value={form.name}
                  onChange={(e) => setField("name", e.target.value)}
                  placeholder="e.g. Q4 Merchant QR Adoption Drive"
                  maxLength={255}
                />
              </FormField>

              <div>
                <label className="mb-2 block text-[12.5px] font-medium text-ink">
                  Campaign objective <span className="text-neg">*</span>
                </label>
                <div className="grid gap-2 sm:grid-cols-2">
                  {OBJECTIVES.map((obj) => (
                    <label
                      key={obj.value}
                      className={`flex cursor-pointer gap-2.5 rounded-[4px] border p-3 transition-colors ${
                        form.objective === obj.value
                          ? "border-primary bg-primary-soft"
                          : "border-line-strong hover:bg-paper"
                      }`}
                    >
                      <input
                        type="radio"
                        name="objective"
                        value={obj.value}
                        checked={form.objective === obj.value}
                        onChange={() => setField("objective", obj.value)}
                        className="mt-0.5 accent-[var(--color-primary)]"
                      />
                      <span>
                        <span className="block text-[13px] font-medium text-ink">
                          {obj.label}
                        </span>
                        <span className="mt-0.5 block text-[12px] text-mute">
                          {obj.desc}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
                {errors.objective && (
                  <p className="mt-1.5 text-[12px] text-neg">
                    {errors.objective}
                  </p>
                )}
              </div>
            </div>
          </Panel>

          {/* Panel 2: Offer & Budget Structure */}
          <Panel className="p-5">
            <SectionHeader title="Offer & Incentive Budget" />
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                id="offer_type"
                label="Offer type"
                required
                error={errors.offer_type}
                hint={
                  OFFER_TYPES.find((o) => o.value === form.offer_type)?.unitHint
                }
              >
                <SelectDropdown
                  id="offer_type"
                  value={form.offer_type}
                  onChange={(val) =>
                    setField("offer_type", val as CampaignOfferType)
                  }
                  options={OFFER_TYPE_OPTIONS}
                  triggerClassName="w-full"
                />
              </FormField>

              <FormField
                id="incentive_value"
                label={
                  form.offer_type === "pct_cashback"
                    ? "Incentive percentage (%)"
                    : form.offer_type === "fee_waiver"
                      ? "Incentive value (0 for waiver)"
                      : "Cashback amount (৳)"
                }
                required
                error={errors.incentive_value}
                hint={
                  form.offer_type === "pct_cashback"
                    ? "Cashback percentage granted per transaction."
                    : form.offer_type === "fee_waiver"
                      ? "Standard waiver value is 0."
                      : "Flat BDT amount credited per conversion."
                }
              >
                <input
                  id="incentive_value"
                  type="number"
                  min={0}
                  step={form.offer_type === "pct_cashback" ? "0.5" : "1"}
                  className={`${inputCls(!!errors.incentive_value)} font-mono`}
                  value={form.incentive_value}
                  onChange={(e) =>
                    setField("incentive_value", Number(e.target.value))
                  }
                  disabled={form.offer_type === "fee_waiver"}
                />
              </FormField>

              <FormField
                id="incentive_cost_bdt"
                label="Unit incentive cost (৳)"
                required
                error={errors.incentive_cost_bdt}
                hint="Expected unit cost in BDT charged against campaign budget."
              >
                <input
                  id="incentive_cost_bdt"
                  type="number"
                  min={0}
                  step="1"
                  className={`${inputCls(!!errors.incentive_cost_bdt)} font-mono`}
                  value={form.incentive_cost_bdt}
                  onChange={(e) =>
                    setField("incentive_cost_bdt", Number(e.target.value))
                  }
                />
              </FormField>

              <FormField
                id="budget_bdt"
                label="Total campaign budget (৳)"
                required
                error={errors.budget_bdt}
                hint="Upper bound in BDT allocated for incentive optimization."
              >
                <input
                  id="budget_bdt"
                  type="number"
                  min={1}
                  step="1000"
                  className={`${inputCls(!!errors.budget_bdt)} font-mono`}
                  value={form.budget_bdt}
                  onChange={(e) =>
                    setField("budget_bdt", Number(e.target.value))
                  }
                />
              </FormField>
            </div>
          </Panel>

          {/* Panel 3: Delivery Channel */}
          <Panel className="p-5">
            <SectionHeader title="Delivery Channel" />
            <div className="space-y-4">
              <div className="grid gap-2 sm:grid-cols-3">
                {CHANNELS.map((ch) => (
                  <label
                    key={ch.value}
                    className={`flex cursor-pointer gap-2.5 rounded-[4px] border p-3 transition-colors ${
                      form.channel === ch.value
                        ? "border-primary bg-primary-soft"
                        : "border-line-strong hover:bg-paper"
                    }`}
                  >
                    <input
                      type="radio"
                      name="channel"
                      value={ch.value}
                      checked={form.channel === ch.value}
                      onChange={() => setField("channel", ch.value)}
                      className="mt-0.5 accent-[var(--color-primary)]"
                    />
                    <span>
                      <span className="block text-[13px] font-medium text-ink">
                        {ch.label}
                      </span>
                      <span className="mt-0.5 block text-[11.5px] text-mute">
                        {ch.desc}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
              {errors.channel && (
                <p className="text-[12px] text-neg">{errors.channel}</p>
              )}
            </div>
          </Panel>

          {/* Data Integrity & Compliance Notice */}
          <div className="rounded-[4px] border border-line bg-paper p-4 text-[12px] leading-relaxed text-mute">
            <span className="font-semibold text-ink">
              Population Evaluation Notice:
            </span>{" "}
            In accordance with CampaignLift integrity constraints, manual
            customer CSV uploads are neither accepted nor allowed. The backend
            scores the eligible population for the active dataset version
            directly through causal inference models.
          </div>
        </div>

        {/* Sidebar Summary & Actions */}
        <aside className="lg:sticky lg:top-18 lg:self-start">
          <Panel className="p-5">
            <SectionHeader title="Scenario Summary" />
            <dl className="space-y-2.5 text-[12.5px]">
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Campaign</dt>
                <dd className="max-w-[170px] truncate text-right font-medium text-ink">
                  {form.name || "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Objective</dt>
                <dd className="text-right text-ink">
                  {OBJECTIVES.find((o) => o.value === form.objective)?.label}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Offer</dt>
                <dd className="text-right font-mono text-[12px] text-ink">
                  {form.offer_type === "fee_waiver"
                    ? "Fee waiver"
                    : form.offer_type === "pct_cashback"
                      ? `${form.incentive_value}% cashback`
                      : bdt(form.incentive_value)}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Unit cost</dt>
                <dd className="text-right font-mono text-[12px] text-ink">
                  {form.incentive_cost_bdt ? bdt(form.incentive_cost_bdt) : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Total budget</dt>
                <dd className="text-right font-mono text-[12px] font-semibold text-ink">
                  {form.budget_bdt ? bdt(form.budget_bdt) : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Max capacity</dt>
                <dd className="text-right font-mono text-[12px] text-ink">
                  {form.budget_bdt && form.incentive_cost_bdt > 0
                    ? `${Math.floor(form.budget_bdt / form.incentive_cost_bdt).toLocaleString()} offers`
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                <dt className="text-mute">Channel</dt>
                <dd className="text-right text-ink uppercase">
                  {form.channel}
                </dd>
              </div>
              {createdCampaign && (
                <div className="flex justify-between gap-3 border-b border-line/70 pb-2">
                  <dt className="text-mute">Campaign ID</dt>
                  <dd className="font-mono text-[11.5px] font-semibold text-pos">
                    {createdCampaign.id}
                  </dd>
                </div>
              )}
            </dl>

            <Button
              type="submit"
              variant="primary"
              className="mt-5 w-full"
              disabled={phase === "saving"}
            >
              {phase === "saving" ? (
                <>
                  <span className="size-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Creating Campaign…
                </>
              ) : createdCampaign ? (
                "Update / Re-create"
              ) : (
                "Create Campaign"
              )}
            </Button>

            {Object.keys(errors).some(
              (k) => errors[(k as keyof CampaignCreateRequest)],
            ) && (
              <p className="mt-2 text-[12px] text-neg" role="alert">
                {Object.values(errors).filter(Boolean).length} field(s) require
                attention.
              </p>
            )}

            {createdCampaign && (
              <div className="mt-4 border-t border-line/70 pt-3">
                <Link
                  to={`/?campaign_id=${createdCampaign.id}`}
                  className="block text-center text-[12.5px] font-medium text-primary hover:underline"
                >
                  Open Campaign in Overview →
                </Link>
              </div>
            )}
          </Panel>
        </aside>
      </form>
    </div>
  )
}
