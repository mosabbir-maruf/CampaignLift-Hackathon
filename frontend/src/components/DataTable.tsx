import { useMemo, useState, type ReactNode } from "react"

export interface Column<T> {
  key: string
  header: string
  align?: "left" | "right"
  width?: string
  sortValue?: (row: T) => number | string
  render: (row: T) => ReactNode
  hideBelow?: "lg"
}

interface Props<T> {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  selectedKey?: string | null
  onSelect?: (row: T) => void
  pageSize?: number
  mobileCard: (row: T) => ReactNode
  caption: string
  initialSort?: { key: string; dir: "asc" | "desc" }
}

export default function DataTable<T>({
  rows,
  columns,
  rowKey,
  selectedKey,
  onSelect,
  pageSize = 25,
  mobileCard,
  caption,
  initialSort,
}: Props<T>) {
  const [sort, setSort] = useState(initialSort ?? null)
  const [page, setPage] = useState(0)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sortValue) return rows
    const f = col.sortValue
    return [...rows].sort((a, b) => {
      const x = f(a),
        y = f(b)
      const r = x < y ? -1 : x > y ? 1 : 0
      return sort.dir === "asc" ? r : -r
    })
  }, [rows, sort, columns])

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const p = Math.min(page, pages - 1)
  const slice = sorted.slice(p * pageSize, p * pageSize + pageSize)

  const toggle = (key: string) => {
    setPage(0)
    setSort((s) =>
      s?.key === key
        ? { key, dir: s.dir === "desc" ? "asc" : "desc" }
        : { key, dir: "desc" },
    )
  }

  return (
    <div>
      {/* Desktop / tablet */}
      <div className="scroll-quiet hidden max-h-[620px] overflow-auto md:block">
        <table className="w-full border-collapse text-[13px]">
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 z-10 bg-surface">
            <tr className="border-b border-line-strong">
              {columns.map((c) => {
                const active = sort?.key === c.key
                return (
                  <th
                    key={c.key}
                    scope="col"
                    style={{ width: c.width }}
                    aria-sort={
                      active
                        ? sort!.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                    className={`h-9 px-3 text-[11.5px] font-medium whitespace-nowrap text-mute ${
                      c.align === "right" ? "text-right" : "text-left"
                    } ${c.hideBelow === "lg" ? "hidden lg:table-cell" : ""}`}
                  >
                    {c.sortValue ? (
                      <button
                        onClick={() => toggle(c.key)}
                        className={`inline-flex items-center gap-1 rounded-sm hover:text-ink ${
                          active ? "text-ink" : ""
                        }`}
                      >
                        {c.header}
                        <span aria-hidden className="font-mono text-[9px]">
                          {active ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}
                        </span>
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {slice.map((row) => {
              const k = rowKey(row)
              const sel = k === selectedKey
              return (
                <tr
                  key={k}
                  tabIndex={onSelect ? 0 : undefined}
                  aria-selected={sel}
                  onClick={() => onSelect?.(row)}
                  onKeyDown={(e) =>
                    (e.key === "Enter" || e.key === " ") &&
                    (e.preventDefault(), onSelect?.(row))
                  }
                  className={`h-9 border-b border-line/70 transition-colors ${
                    onSelect ? "cursor-pointer" : ""
                  } ${
                    sel
                      ? "bg-primary-soft shadow-[inset_2px_0_0_var(--color-primary)]"
                      : "hover:bg-paper"
                  }`}
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={`px-3 ${
                        c.align === "right" ? "text-right" : ""
                      } ${c.hideBelow === "lg" ? "hidden lg:table-cell" : ""}`}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile */}
      <ul className="divide-y divide-line md:hidden">
        {slice.map((row) => (
          <li key={rowKey(row)}>
            <button
              onClick={() => onSelect?.(row)}
              className="block w-full px-4 py-3 text-left active:bg-paper"
            >
              {mobileCard(row)}
            </button>
          </li>
        ))}
      </ul>

      <nav
        aria-label="Pagination"
        className="flex items-center justify-between border-t border-line px-3 py-2 text-[12px] text-mute"
      >
        <span className="tnum font-mono">
          {sorted.length === 0 ? 0 : p * pageSize + 1}–
          {Math.min(sorted.length, (p + 1) * pageSize)} of{" "}
          {sorted.length.toLocaleString()}
        </span>
        <div className="flex items-center gap-1">
          <button
            disabled={p === 0}
            onClick={() => setPage(p - 1)}
            className="h-7 rounded-[3px] px-2 hover:bg-sunken disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="tnum px-2 font-mono">
            {p + 1} / {pages}
          </span>
          <button
            disabled={p >= pages - 1}
            onClick={() => setPage(p + 1)}
            className="h-7 rounded-[3px] px-2 hover:bg-sunken disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </nav>
    </div>
  )
}
