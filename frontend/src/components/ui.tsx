import { useEffect, type ReactNode } from "react"
import type { ResourceStatus } from "../hooks/useResource"
import { pct, pp, upliftDirection, STATUS_META, type Tone } from "../lib/format"
import type { TargetingStatus } from "../api/types"

const toneText: Record<Tone, string> = {
  pos: "text-pos",
  neg: "text-neg",
  warn: "text-warn",
  neu: "text-neu",
  primary: "text-primary",
}
const toneSoft: Record<Tone, string> = {
  pos: "bg-pos-soft text-pos",
  neg: "bg-neg-soft text-neg",
  warn: "bg-warn-soft text-warn",
  neu: "bg-neu-soft text-neu",
  primary: "bg-primary-soft text-primary",
}
const toneDot: Record<Tone, string> = {
  pos: "bg-pos",
  neg: "bg-neg",
  warn: "bg-warn",
  neu: "bg-neu",
  primary: "bg-primary",
}

export function PageHeader({
  step,
  title,
  lede,
  actions,
}: {
  step: string
  title: string
  lede?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <p className="font-mono text-[11px] tracking-wider text-mute uppercase">
          Step {step}
        </p>
        <h1 className="mt-1 text-[26px] leading-tight font-semibold tracking-tight text-ink">
          {title}
        </h1>
        {lede && (
          <p className="mt-2 text-[14px] leading-relaxed text-ink-2">{lede}</p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </header>
  )
}

export function SectionHeader({
  title,
  meta,
  children,
}: {
  title: string
  meta?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="text-[13px] font-semibold tracking-wide text-ink uppercase">
        {title}
      </h2>
      <div className="flex items-center gap-3 text-[12px] text-mute">
        {meta}
        {children}
      </div>
    </div>
  )
}

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-[5px] border border-line bg-surface ${className}`}
    >
      {children}
    </section>
  )
}

export function MetricBlock({
  label,
  value,
  note,
  tone,
}: {
  label: string
  value: ReactNode
  note?: ReactNode
  tone?: Tone
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[12px] text-mute">{label}</dt>
      <dd
        className={`tnum mt-1 font-mono text-[20px] leading-none font-medium ${
          tone ? toneText[tone] : "text-ink"
        }`}
      >
        {value}
      </dd>
      {note && <dd className="mt-1.5 text-[12px] text-mute">{note}</dd>}
    </div>
  )
}

export function Badge({
  tone = "neu",
  children,
  dot = true,
}: {
  tone?: Tone
  children: ReactNode
  dot?: boolean
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[3px] px-1.5 py-0.5 text-[11.5px] font-medium whitespace-nowrap ${toneSoft[tone]}`}
    >
      {dot && (
        <span
          aria-hidden
          className={`size-1.5 rounded-full ${toneDot[tone]}`}
        />
      )}
      {children}
    </span>
  )
}

export function StatusBadge({
  status,
  short,
}: {
  status: TargetingStatus
  short?: boolean
}) {
  const m = STATUS_META[status]
  return <Badge tone={m.tone}>{short ? m.short : m.label}</Badge>
}

export function IllustrativeTag({ show = true }: { show?: boolean }) {
  if (!show) return null
  return (
    <span
      title="Example data for interface review — not campaign results"
      className="inline-flex items-center rounded-[3px] border border-dashed border-warn/60 px-1.5 py-px font-mono text-[10.5px] tracking-wide text-warn uppercase"
    >
      Illustrative
    </span>
  )
}

export function UpliftIndicator({
  value,
  size = "md",
}: {
  value: number | null
  size?: "md" | "lg"
}) {
  if (value == null) return <span className="text-mute">—</span>
  const dir = upliftDirection(value)
  const glyph = dir === "up" ? "▲" : dir === "down" ? "▼" : "◆"
  const tone =
    dir === "up" ? "text-pos" : dir === "down" ? "text-neg" : "text-neu"
  const label =
    dir === "up" ? "positive" : dir === "down" ? "negative" : "near zero"
  return (
    <span
      className={`tnum inline-flex items-center gap-1 font-mono font-medium ${tone} ${
        size === "lg" ? "text-[22px]" : "text-[13px]"
      }`}
      aria-label={`Uplift ${pp(value)}, ${label}`}
    >
      <span
        aria-hidden
        className={size === "lg" ? "text-[13px]" : "text-[9px]"}
      >
        {glyph}
      </span>
      {pp(value)}
    </span>
  )
}

/** Treatment vs control on a shared 0–100% axis. The connecting segment IS the uplift. */
export function ProbabilityDumbbell({
  pTreat,
  pControl,
  height = "sm",
  axis = false,
}: {
  pTreat: number
  pControl: number
  height?: "sm" | "lg"
  axis?: boolean
}) {
  const lo = Math.min(pTreat, pControl) * 100
  const hi = Math.max(pTreat, pControl) * 100
  const dir = upliftDirection(pTreat - pControl)
  const line = dir === "up" ? "bg-pos" : dir === "down" ? "bg-neg" : "bg-neu"
  const dot = height === "lg" ? "size-3.5" : "size-2.5"
  return (
    <div
      className="w-full"
      role="img"
      aria-label={`Treatment ${pct(pTreat)}, control ${pct(pControl)}`}
    >
      <div className={`relative ${height === "lg" ? "h-6" : "h-4"}`}>
        <div className="absolute inset-x-0 top-1/2 h-px bg-line" />
        {axis &&
          [25, 50, 75].map((t) => (
            <div
              key={t}
              className="absolute top-1/4 h-1/2 w-px bg-line"
              style={{ left: `${t}%` }}
            />
          ))}
        <div
          className={`absolute top-1/2 -translate-y-1/2 ${
            height === "lg" ? "h-[3px]" : "h-[2px]"
          } ${line}`}
          style={{ left: `${lo}%`, width: `${hi - lo}%` }}
        />
        <span
          className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-2 bg-surface ${dot}`}
          style={{ left: `${pControl * 100}%` }}
        />
        <span
          className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-ink ${dot}`}
          style={{ left: `${pTreat * 100}%` }}
        />
      </div>
      {axis && (
        <div className="tnum mt-1 flex justify-between font-mono text-[10px] text-mute">
          <span>0%</span>
          <span>25%</span>
          <span>50%</span>
          <span>75%</span>
          <span>100%</span>
        </div>
      )}
    </div>
  )
}

export function DumbbellLegend() {
  return (
    <span className="flex items-center gap-3 text-[11.5px] text-mute">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-ink" />
        Treatment (offer)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border-2 border-ink-2 bg-surface" />
        Control (no offer)
      </span>
    </span>
  )
}

export function Button({
  variant = "secondary",
  className = "",
  ...p
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost"
}) {
  const v = {
    primary:
      "bg-primary text-white hover:bg-primary-hover disabled:bg-line-strong",
    secondary:
      "border border-line-strong bg-surface text-ink hover:bg-sunken disabled:text-mute",
    ghost: "text-ink-2 hover:bg-sunken",
  }[variant]
  return (
    <button
      {...p}
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-[4px] px-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed ${v} ${className}`}
    />
  )
}

export function FormField({
  id,
  label,
  required,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  required?: boolean
  hint?: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[12.5px] font-medium text-ink">
        {label}{" "}
        {required ? (
          <span className="text-neg" aria-hidden>
            *
          </span>
        ) : (
          <span className="font-normal text-mute">(optional)</span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${id}-err`} className="text-[12px] text-neg">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[12px] text-mute">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export const inputCls = (invalid?: boolean) =>
  `h-9 w-full rounded-[4px] border bg-surface px-2.5 text-[13.5px] text-ink placeholder:text-mute/70 focus:outline-2 focus:outline-primary focus:-outline-offset-1 ${
    invalid ? "border-neg" : "border-line-strong"
  }`

/* ---------- States ---------- */

export function LoadingState({
  rows = 5,
  label = "Loading",
}: {
  rows?: number
  label?: string
}) {
  return (
    <div role="status" aria-label={label} className="space-y-2.5 p-5">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex animate-pulse-soft items-center gap-4"
          style={{ animationDelay: `${i * 90}ms` }}
        >
          <div className="h-3 w-24 rounded-sm bg-sunken" />
          <div className="h-3 flex-1 rounded-sm bg-sunken" />
          <div className="h-3 w-16 rounded-sm bg-sunken" />
        </div>
      ))}
      <p className="pt-1 font-mono text-[11px] text-mute">{label}…</p>
    </div>
  )
}

function StateFrame({
  tone,
  title,
  children,
  action,
}: {
  tone: Tone
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div
      className={`m-5 border-l-2 py-1 pl-4 ${
        tone === "neg"
          ? "border-neg"
          : tone === "warn"
            ? "border-warn"
            : "border-line-strong"
      }`}
    >
      <p className={`text-[13.5px] font-semibold ${toneText[tone]}`}>{title}</p>
      <div className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
        {children}
      </div>
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export const EmptyState = (p: {
  title: string
  children: ReactNode
  action?: ReactNode
}) => <StateFrame tone="neu" {...p} />
export const ErrorState = ({
  message,
  onRetry,
}: {
  message?: string | null
  onRetry?: () => void
}) => (
  <StateFrame
    tone="neg"
    title="Could not load this data"
    action={onRetry && <Button onClick={onRetry}>Retry request</Button>}
  >
    {message ?? "The request failed."} No substitute values are shown.
  </StateFrame>
)
export const InsufficientState = ({ children }: { children?: ReactNode }) => (
  <StateFrame tone="warn" title="Insufficient support">
    {children ??
      "The backend reported too few observations to produce reliable estimates for this view. Values are withheld rather than estimated."}
  </StateFrame>
)

export function Resource<T>({
  r,
  empty,
  children,
  rows,
}: {
  r: {
    status: ResourceStatus
    data: T | null
    error: string | null
    retry: () => void
  }
  empty?: ReactNode
  rows?: number
  children: (d: T) => ReactNode
}) {
  if (r.status === "loading") return <LoadingState rows={rows} />
  if (r.status === "error")
    return <ErrorState message={r.error} onRetry={r.retry} />
  if (r.status === "insufficient") return <InsufficientState />
  if (r.status === "empty" || !r.data)
    return (
      <>
        {empty ?? (
          <EmptyState title="Data not loaded">
            Data is not loaded. Connect the backend service or select a preview
            state.
          </EmptyState>
        )}
      </>
    )
  return <>{children(r.data)}</>
}

/* ---------- Drawer ---------- */

export function Drawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", k)
    return () => window.removeEventListener("keydown", k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        aria-label="Close panel"
        className="absolute inset-0 animate-fade bg-ink/25"
        onClick={onClose}
      />
      <aside className="absolute inset-y-0 right-0 flex w-full max-w-md animate-slide flex-col border-l border-line bg-surface">
        <div className="flex h-12 items-center justify-between border-b border-line px-5">
          <h2 className="text-[14px] font-semibold">{title}</h2>
          <Button
            variant="ghost"
            onClick={onClose}
            autoFocus
            aria-label="Close"
          >
            Close ✕
          </Button>
        </div>
        <div className="scroll-quiet flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>
  )
}
