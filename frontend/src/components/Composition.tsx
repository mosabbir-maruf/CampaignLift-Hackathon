import type { AudienceSummary, TargetingStatus } from "../api/types"
import { STATUS_META, STATUS_ORDER } from "../lib/format"

const fill: Record<string, string> = {
  pos: "bg-pos",
  neg: "bg-neg",
  warn: "bg-warn [background-image:repeating-linear-gradient(45deg,transparent_0_3px,rgba(255,255,255,.35)_3px_6px)]",
  neu: "bg-neu/70",
}

/** Audience composition by backend-assigned targeting status. */
export default function Composition({
  summary,
  onPick,
  active,
}: {
  summary: AudienceSummary
  onPick?: (s: TargetingStatus) => void
  active?: TargetingStatus | "all"
}) {
  const total = summary.eligible_customers
  return (
    <div>
      <div
        className="flex h-3 w-full gap-px overflow-hidden rounded-[2px]"
        role="img"
        aria-label="Audience composition by targeting status"
      >
        {STATUS_ORDER.map((s) => {
          const w = (summary.by_status[s] / total) * 100
          const dim = active && active !== "all" && active !== s
          const tone =
            s === "likely_without_offer" ? "bg-neu" : fill[STATUS_META[s].tone]
          return (
            <div
              key={s}
              className={`${tone} transition-opacity ${
                dim ? "opacity-25" : ""
              }`}
              style={{ width: `${w}%` }}
            />
          )
        })}
      </div>
      <ul className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-5">
        {STATUS_ORDER.map((s) => {
          const n = summary.by_status[s]
          const m = STATUS_META[s]
          const Tag = onPick ? "button" : "div"
          return (
            <li key={s}>
              <Tag
                onClick={onPick ? () => onPick(s) : undefined}
                className={`flex w-full items-baseline justify-between gap-2 text-left text-[12px] ${
                  onPick ? "rounded-sm hover:text-ink" : ""
                } ${active === s ? "font-semibold text-ink" : "text-ink-2"}`}
              >
                <span className="flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className={`size-2 rounded-[1px] ${
                      s === "likely_without_offer" ? "bg-neu" : fill[m.tone]
                    }`}
                  />
                  {m.label}
                </span>
                <span className="tnum font-mono text-mute">
                  {((n / total) * 100).toFixed(0)}%
                </span>
              </Tag>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
