import type { TargetingStatus } from "../api/types"

export const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(d)}%`

export const pp = (v: number | null | undefined, d = 1) => {
  if (v == null) return "—"
  const s = (Math.abs(v) * 100).toFixed(d)
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${s} pp`
}

export const num = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("en-US")

export const bdt = (v: number | null | undefined) =>
  v == null ? "—" : `৳${Math.round(v).toLocaleString("en-US")}`

export type Tone = "pos" | "neg" | "warn" | "neu" | "primary"

/** Display-only direction for glyphs. Bands are for visual reading, not decisions. */
export const upliftDirection = (v: number): "up" | "down" | "flat" =>
  v >= 0.02 ? "up" : v <= -0.02 ? "down" : "flat"

export const STATUS_META: Record<TargetingStatus, {
  label: string
  tone: Tone
  short: string
}> = {
  high_incremental: {
    label: "High incremental potential",
    short: "Persuadable",
    tone: "pos",
  },
  low_incremental: {
    label: "Low incremental potential",
    short: "Low effect",
    tone: "neu",
  },
  likely_without_offer: {
    label: "Likely without offer",
    short: "Responds anyway",
    tone: "neu",
  },
  negative_uplift: {
    label: "Potential negative uplift",
    short: "Avoid",
    tone: "neg",
  },
  insufficient_support: {
    label: "Insufficient support",
    short: "Low support",
    tone: "warn",
  },
}

export const STATUS_ORDER: TargetingStatus[] = [
  "high_incremental",
  "likely_without_offer",
  "low_incremental",
  "negative_uplift",
  "insufficient_support",
]
