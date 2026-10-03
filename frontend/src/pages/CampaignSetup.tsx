import { useState } from "react"
import type { CampaignConfig, StrategyKey } from "../api/types"
import {
  Button,
  FormField,
  PageHeader,
  Panel,
  SectionHeader,
  inputCls,
} from "../components/ui"
import { usePreview } from "../hooks/useResource"
import { bdt } from "../lib/format"

type Errors = Partial<Record<keyof CampaignConfig, string>>
type Phase = "idle" | "saving" | "success" | "error"

const INITIAL: CampaignConfig = {
  name: "",
  objective: "",
  offer_type: "Cashback",
  offer_value: 0,
  start_date: "",
  end_date: "",
  budget: 0,
  eligibility_context: "",
  targeting_strategy: "uplift",
}

const STRATEGIES: { key: StrategyKey label: string desc: string }[] = [
  {
    key: "uplift",
    label: "Uplift targeting",
    desc: "Rank by expected incremental effect. Recommended.",
  },
  {
    key: "response",
    label: "Response-based",
    desc: "Rank by likelihood to respond when offered.",
  },
  {
    key: "random",
    label: "Random",
    desc: "Uniform sample. Useful as a baseline.",
  },
]

function validate(c: CampaignConfig): Errors {
  const e: Errors = {}
  if (!c.name.trim()) e.name = "Enter a campaign name."
  if (!c.objective.trim())
    e.objective = "Describe what the campaign should change."
  if (!(c.offer_value > 0))
    e.offer_value = "Offer value must be greater than 0."
  if (!c.start_date) e.start_date = "Choose a start date."
  if (!c.end_date) e.end_date = "Choose an end date."
  else if (c.start_date && c.end_date <= c.start_date)
    e.end_date = "End date must be after the start date."
  if (!(c.budget > 0)) e.budget = "Budget must be greater than 0."
  else if (c.offer_value > 0 && c.budget < c.offer_value)
    e.budget = "Budget is smaller than a single offer."
  if (!c.eligibility_context.trim())
    e.eligibility_context =
      "Describe the eligibility rule the backend should apply."
  return e
}

export default function CampaignSetup() {
  const [c, setC] = useState(INITIAL)
  const [errors, setErrors] = useState<Errors>({})
  const [phase, setPhase] = useState<Phase>("idle")
  const { state } = usePreview()

  const set = <K extends keyof CampaignConfig>(k: K, v: CampaignConfig[K]) => {
    setC((p) => ({ ...p, [k]: v }))
    if (errors[k]) setErrors((p) => ({ ...p, [k]: undefined }))
    if (phase !== "idle" && phase !== "saving") setPhase("idle")
  }

  const submit = (ev: React.FormEvent) => {
    ev.preventDefault()
    const e = validate(c)
    setErrors(e)
    if (Object.keys(e).length) {
      document.getElementById(Object.keys(e)[0])?.focus()
      return
    }
    setPhase("saving")
    // TODO(integration): POST the CampaignConfig to the backend campaign-creation endpoint.
    setTimeout(() => setPhase(state === "error" ? "error" : "success"), 900)
  }

  const field = (id: keyof CampaignConfig) => ({
    id,
    "aria-invalid": !!errors[id],
    "aria-describedby": errors[id] ? `${id}-err` : `${id}-hint`,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        step="02"
        title="Campaign Setup"
        lede="Define the campaign. Eligible customers are resolved by the backend from the eligibility context — no customer upload is needed."
      />

      <form
        onSubmit={submit}
        noValidate
        className="grid gap-6 lg:grid-cols-[1fr_320px]"
      >
        <div className="space-y-6">
          {phase === "error" && (
            <div
              role="alert"
              className="border-l-2 border-neg bg-neg-soft px-4 py-3 text-[13px] text-neg"
            >
              <p className="font-semibold">Campaign was not created</p>
              <p className="mt-0.5 text-ink-2">
                The backend rejected the request (preview error state). Your
                inputs are preserved — retry when the service is available.
              </p>
            </div>
          )}
          {phase === "success" && (
            <div
              role="status"
              className="border-l-2 border-pos bg-pos-soft px-4 py-3 text-[13px]"
            >
              <p className="font-semibold text-pos">
                Campaign configuration ready
              </p>
              <p className="mt-0.5 text-ink-2">
                In preview mode nothing was sent. Once connected, the backend
                will create the campaign and begin scoring eligible customers.
              </p>
            </div>
          )}

          <Panel className="p-5">
            <SectionHeader title="Campaign" />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <FormField
                  id="name"
                  label="Campaign name"
                  required
                  error={errors.name}
                  hint="Shown to analysts across CampaignLift."
                >
                  <input
                    {...field("name")}
                    className={inputCls(!!errors.name)}
                    value={c.name}
                    onChange={(e) => set("name", e.target.value)}
                    placeholder="e.g. Q4 Cash-Out Reactivation"
                  />
                </FormField>
              </div>
              <div className="md:col-span-2">
                <FormField
                  id="objective"
                  label="Campaign objective"
                  required
                  error={errors.objective}
                  hint="The behaviour the offer is meant to change."
                >
                  <input
                    {...field("objective")}
                    className={inputCls(!!errors.objective)}
                    value={c.objective}
                    onChange={(e) => set("objective", e.target.value)}
                    placeholder="e.g. Reactivate dormant cash-out users"
                  />
                </FormField>
              </div>
              <FormField
                id="start_date"
                label="Start date"
                required
                error={errors.start_date}
              >
                <input
                  type="date"
                  {...field("start_date")}
                  className={inputCls(!!errors.start_date)}
                  value={c.start_date}
                  onChange={(e) => set("start_date", e.target.value)}
                />
              </FormField>
              <FormField
                id="end_date"
                label="End date"
                required
                error={errors.end_date}
              >
                <input
                  type="date"
                  {...field("end_date")}
                  className={inputCls(!!errors.end_date)}
                  value={c.end_date}
                  onChange={(e) => set("end_date", e.target.value)}
                />
              </FormField>
            </div>
          </Panel>

          <Panel className="p-5">
            <SectionHeader title="Offer & budget" />
            <div className="grid gap-4 md:grid-cols-3">
              <FormField id="offer_type" label="Offer type" required>
                <select
                  id="offer_type"
                  className={inputCls()}
                  value={c.offer_type}
                  onChange={(e) => set("offer_type", e.target.value)}
                >
                  <option>Cashback</option>
                  <option>Fee waiver</option>
                  <option>Bonus airtime</option>
                  <option>Merchant discount</option>
                </select>
              </FormField>
              <FormField
                id="offer_value"
                label="Offer value (৳)"
                required
                error={errors.offer_value}
                hint="Per customer."
              >
                <input
                  type="number"
                  min={0}
                  inputMode="decimal"
                  {...field("offer_value")}
                  className={`${inputCls(!!errors.offer_value)} tnum font-mono`}
                  value={c.offer_value || ""}
                  onChange={(e) => set("offer_value", Number(e.target.value))}
                  placeholder="50"
                />
              </FormField>
              <FormField
                id="budget"
                label="Total budget (৳)"
                required
                error={errors.budget}
                hint="Upper bound for optimization."
              >
                <input
                  type="number"
                  min={0}
                  inputMode="decimal"
                  {...field("budget")}
                  className={`${inputCls(!!errors.budget)} tnum font-mono`}
                  value={c.budget || ""}
                  onChange={(e) => set("budget", Number(e.target.value))}
                  placeholder="500000"
                />
              </FormField>
            </div>
          </Panel>

          <Panel className="p-5">
            <SectionHeader title="Audience & targeting" />
            <div className="space-y-5">
              <FormField
                id="eligibility_context"
                label="Eligibility context"
                required
                error={errors.eligibility_context}
                hint="Passed to the backend, which resolves the eligible customer set."
              >
                <textarea
                  {...field("eligibility_context")}
                  rows={3}
                  className={`${inputCls(!!errors.eligibility_context)} h-auto py-2`}
                  value={c.eligibility_context}
                  onChange={(e) => set("eligibility_context", e.target.value)}
                  placeholder="e.g. No cash-out in last 60 days, active wallet, KYC verified"
                />
              </FormField>
              <fieldset>
                <legend className="mb-2 text-[12.5px] font-medium">
                  Targeting strategy{" "}
                  <span className="text-neg" aria-hidden>
                    *
                  </span>
                </legend>
                <div className="grid gap-2 md:grid-cols-3">
                  {STRATEGIES.map((s) => (
                    <label
                      key={s.key}
                      className={`flex cursor-pointer gap-2.5 rounded-[4px] border p-3 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-primary ${
                        c.targeting_strategy === s.key
                          ? "border-primary bg-primary-soft"
                          : "border-line-strong hover:bg-paper"
                      }`}
                    >
                      <input
                        type="radio"
                        name="strategy"
                        className="mt-0.5 accent-[var(--color-primary)]"
                        checked={c.targeting_strategy === s.key}
                        onChange={() => set("targeting_strategy", s.key)}
                      />
                      <span>
                        <span className="block text-[13px] font-medium">
                          {s.label}
                        </span>
                        <span className="mt-0.5 block text-[12px] text-mute">
                          {s.desc}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          </Panel>
        </div>

        <aside className="lg:sticky lg:top-18 lg:self-start">
          <Panel className="p-5">
            <SectionHeader title="Request summary" />
            <dl className="space-y-2 text-[12.5px]">
              {[
                ["Name", c.name || "—"],
                [
                  "Offer",
                  c.offer_value
                    ? `${c.offer_type} · ${bdt(c.offer_value)}`
                    : "—",
                ],
                ["Budget", c.budget ? bdt(c.budget) : "—"],
                [
                  "Max offers",
                  c.budget && c.offer_value
                    ? `${Math.floor(c.budget / c.offer_value).toLocaleString()} (budget ÷ value)`
                    : "—",
                ],
                [
                  "Window",
                  c.start_date && c.end_date
                    ? `${c.start_date} → ${c.end_date}`
                    : "—",
                ],
                [
                  "Strategy",
                  STRATEGIES.find((s) => s.key === c.targeting_strategy)!.label,
                ],
              ].map(([k, v]) => (
                <div
                  key={k}
                  className="flex justify-between gap-3 border-b border-line/70 pb-2"
                >
                  <dt className="text-mute">{k}</dt>
                  <dd className="tnum text-right font-mono text-[12px]">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-[12px] leading-relaxed text-mute">
              After creation the backend scores each eligible customer with
              p_treat, p_control and uplift. Review them in Audience.
            </p>
            <Button
              type="submit"
              variant="primary"
              className="mt-4 w-full"
              disabled={phase === "saving"}
            >
              {phase === "saving" ? (
                <>
                  <span className="size-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Creating campaign…
                </>
              ) : (
                "Create campaign"
              )}
            </Button>
            {Object.keys(errors).some((k) => errors[(k as keyof Errors)]) && (
              <p className="mt-2 text-[12px] text-neg" role="alert">
                {Object.values(errors).filter(Boolean).length} field(s) need
                attention.
              </p>
            )}
          </Panel>
        </aside>
      </form>
    </div>
  )
}
