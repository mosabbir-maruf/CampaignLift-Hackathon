import type { UpliftDecile } from "../api/types"
import { pct, pp } from "../lib/format"

/** Renders backend-supplied uplift_deciles as a diverging bar chart. No binning happens here. */
export default function DecileChart({
  deciles,
  compact = false,
}: {
  deciles: UpliftDecile[]
  compact?: boolean
}) {
  const max = Math.max(...deciles.map((d) => Math.abs(d.mean_uplift)), 0.01)
  const h = compact ? 120 : 200
  const half = h / 2
  return (
    <figure>
      <div className="flex gap-2">
        <div
          className="tnum flex w-12 flex-col justify-between py-0 text-right font-mono text-[10px] text-mute"
          style={{ height: h }}
          aria-hidden
        >
          <span>{pp(max, 0)}</span>
          <span>0</span>
          <span>{pp(-max, 0)}</span>
        </div>
        <div className="relative flex-1" style={{ height: h }}>
          <div
            className="absolute inset-x-0 border-t border-ink-2"
            style={{ top: half }}
          />
          <ol
            className="absolute inset-0 grid gap-1.5"
            style={{
              gridTemplateColumns: `repeat(${deciles.length}, minmax(0,1fr))`,
            }}
          >
            {deciles.map((d) => {
              const v = d.mean_uplift
              const bh = (Math.abs(v) / max) * (half - 2)
              const pos = v >= 0
              return (
                <li
                  key={d.decile}
                  className="group relative"
                  aria-label={`Decile ${d.decile}: mean uplift ${pp(v)}${
                    d.mean_p_treat !== undefined
                      ? `, treatment ${pct(d.mean_p_treat)}`
                      : ""
                  }${
                    d.mean_p_control !== undefined
                      ? `, control ${pct(d.mean_p_control)}`
                      : ""
                  }`}
                  tabIndex={0}
                >
                  <div
                    className={`absolute inset-x-0 transition-opacity group-hover:opacity-80 ${
                      pos ? "bg-pos" : "bg-neg"
                    } ${Math.abs(v) < 0.02 ? "opacity-50" : ""}`}
                    style={
                      pos
                        ? { bottom: half, height: Math.max(bh, 1) }
                        : { top: half, height: Math.max(bh, 1) }
                    }
                  />
                  {!compact && (
                    <span
                      className={`tnum absolute inset-x-0 text-center font-mono text-[10px] ${
                        pos ? "text-pos" : "text-neg"
                      }`}
                      style={
                        pos ? { bottom: half + bh + 3 } : { top: half + bh + 3 }
                      }
                    >
                      {pp(v, 0).replace(" pp", "")}
                    </span>
                  )}
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden w-40 -translate-x-1/2 rounded-[4px] bg-ink px-2.5 py-2 text-[11px] text-white group-hover:block group-focus:block">
                    <p className="font-semibold">Decile {d.decile}</p>
                    <p className="tnum font-mono">Mean Uplift {pp(v)}</p>
                    {d.min_uplift !== undefined &&
                      d.max_uplift !== undefined && (
                        <p className="tnum font-mono text-[10px] opacity-70">
                          Range: {pp(d.min_uplift)} → {pp(d.max_uplift)}
                        </p>
                      )}
                    {d.mean_p_treat !== undefined &&
                      d.mean_p_control !== undefined && (
                        <p className="tnum font-mono opacity-70">
                          T {pct(d.mean_p_treat)} · C {pct(d.mean_p_control)}
                        </p>
                      )}
                    <p className="tnum font-mono opacity-70">
                      {(d.customer_count ?? d.customers ?? 0).toLocaleString()}{" "}
                      customers
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
        </div>
      </div>
      <div
        className="ml-14 grid gap-1.5 pt-2"
        style={{
          gridTemplateColumns: `repeat(${deciles.length}, minmax(0,1fr))`,
        }}
        aria-hidden
      >
        {deciles.map((d) => (
          <span
            key={d.decile}
            className="tnum text-center font-mono text-[10px] text-mute"
          >
            D{d.decile}
          </span>
        ))}
      </div>
      {!compact && (
        <figcaption className="mt-2 ml-14 text-[11.5px] text-mute">
          Customers ranked by predicted uplift, highest (D1) to lowest (D10).
          Bars show mean uplift per decile as supplied by the backend.
        </figcaption>
      )}
    </figure>
  )
}
