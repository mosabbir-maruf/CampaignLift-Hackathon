import { useState, type ReactNode } from "react"
import { Link, useRoute } from "../lib/router"
import { usePreview, type ResourceStatus } from "../hooks/useResource"
import { hasBackend } from "../api/client"
import { SelectDropdown, type SelectOption } from "./ui"

export const NAV = [
  {
    group: "Configure",
    items: [
      { n: "01", path: "/", label: "Overview" },
      { n: "02", path: "/setup", label: "Campaign Setup" },
    ],
  },
  {
    group: "Analyze",
    items: [
      { n: "03", path: "/audience", label: "Audience" },
      { n: "04", path: "/uplift", label: "Uplift Analysis" },
      { n: "05", path: "/strategy", label: "Strategy Comparison" },
    ],
  },
  {
    group: "Decide",
    items: [
      { n: "06", path: "/budget", label: "Budget Optimization" },
      { n: "07", path: "/explain", label: "Customer Explanation" },
    ],
  },
  {
    group: "Validate",
    items: [
      { n: "08", path: "/experiment", label: "Experiment Intelligence" },
      { n: "09", path: "/copilot", label: "Campaign Copilot" },
    ],
  },
]

function NavList({
  onNavigate,
  rail = false,
}: {
  onNavigate?: () => void
  rail?: boolean
}) {
  const { path } = useRoute()
  return (
    <nav aria-label="Workflow" className="flex flex-col gap-5">
      {NAV.map((g) => (
        <div key={g.group}>
          <p
            className={`mb-1.5 px-3 font-mono text-[10px] tracking-[0.14em] text-rail-text/60 uppercase ${
              rail ? "xl:block hidden" : ""
            }`}
          >
            {g.group}
          </p>
          <ul className="flex flex-col gap-px">
            {g.items.map((it) => {
              const active = path === it.path
              return (
                <li key={it.path}>
                  <Link
                    to={it.path}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={it.label}
                    className={`relative flex h-8 items-center gap-3 rounded-[4px] px-3 text-[13px] transition-colors ${
                      active
                        ? "bg-rail-2 text-white"
                        : "text-rail-text hover:bg-rail-2/60 hover:text-white"
                    } ${rail ? "justify-center xl:justify-start" : ""}`}
                  >
                    {active && (
                      <span
                        aria-hidden
                        className="absolute inset-y-1.5 left-0 w-[2px] bg-[#7cc4d1]"
                      />
                    )}
                    <span
                      className={`tnum font-mono text-[11px] ${
                        active ? "text-[#7cc4d1]" : "text-rail-text/60"
                      }`}
                    >
                      {it.n}
                    </span>
                    <span className={rail ? "hidden xl:inline" : ""}>
                      {it.label}
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg
        aria-hidden
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        className="shrink-0"
      >
        <line
          x1="5"
          y1="15"
          x2="15"
          y2="5"
          stroke="#2ED8A3"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <circle cx="5" cy="15" r="4.2" fill="#1DB584" />
        <circle cx="15" cy="5" r="4.2" fill="#4EEDB9" />
      </svg>
      {!compact && (
        <div className="leading-none">
          <p className="text-[14px] font-semibold tracking-tight text-white">
            CampaignLift
          </p>
          <p className="mt-1 font-mono text-[9.5px] tracking-[0.14em] text-rail-text/70 uppercase">
            Decision Support
          </p>
        </div>
      )}
    </div>
  )
}

const STATE_OPTIONS: SelectOption<ResourceStatus>[] = [
  { value: "ready", label: "ready", dot: "bg-pos" },
  { value: "loading", label: "loading", dot: "bg-primary animate-pulse" },
  { value: "empty", label: "empty", dot: "bg-mute" },
  { value: "error", label: "error", dot: "bg-neg" },
  { value: "insufficient", label: "insufficient", dot: "bg-warn" },
]

export default function AppShell({
  children,
  role = null,
  onLogout,
}: {
  children: ReactNode
  role?: "manager" | "viewer" | null
  onLogout?: () => void
}) {
  const [menu, setMenu] = useState(false)
  const { state, setState } = usePreview()
  const { path } = useRoute()
  const isLoginPage = path === "/login"

  return (
    <div className="flex min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Rail / sidebar: hide on login page */}
      {!isLoginPage && (
        <aside className="sticky top-0 hidden h-screen w-16 shrink-0 flex-col bg-rail px-2 py-4 md:flex xl:w-60 xl:px-3">
          <div className="mb-7 flex justify-center px-1 xl:justify-start xl:px-2">
            <span className="xl:hidden">
              <Wordmark compact />
            </span>
            <span className="hidden xl:block">
              <Wordmark />
            </span>
          </div>
          <div className="scroll-quiet flex-1 overflow-y-auto">
            <NavList rail />
          </div>
          <div className="mt-4 hidden border-t border-rail-2 px-2 pt-3 text-[11px] leading-relaxed text-rail-text/70 xl:block">
            Treat the persuadables. Sure things sell themselves.
          </div>
        </aside>
      )}

      {/* Mobile menu */}
      {menu && !isLoginPage && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
        >
          <button
            className="absolute inset-0 bg-ink/40"
            aria-label="Close menu"
            onClick={() => setMenu(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72 animate-fade overflow-y-auto bg-rail p-4">
            <div className="mb-6 flex items-center justify-between">
              <Wordmark />
              <button
                onClick={() => setMenu(false)}
                className="px-2 text-rail-text"
                aria-label="Close menu"
              >
                ✕
              </button>
            </div>
            <NavList onNavigate={() => setMenu(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur-sm lg:px-6">
          {!isLoginPage && (
            <button
              onClick={() => setMenu(true)}
              className="-ml-1 flex h-8 items-center gap-2 rounded-[4px] px-2 text-[13px] font-medium md:hidden"
              aria-label="Open navigation"
            >
              <span aria-hidden className="flex flex-col gap-[3px]">
                <span className="h-px w-4 bg-ink" />
                <span className="h-px w-4 bg-ink" />
                <span className="h-px w-4 bg-ink" />
              </span>
              Menu
            </button>
          )}
          <div className="flex min-w-0 items-center gap-2 text-[13px]">
            {isLoginPage && <Wordmark />}
            <span className="font-semibold tracking-tight text-ink">
              Decision support
            </span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {!hasBackend && !isLoginPage && (
              <div className="hidden items-center gap-2 text-[11.5px] text-mute lg:flex">
                <span className="flex items-center gap-1.5">
                  <span className="size-1.5 rounded-full bg-warn" />
                  Preview data · state
                </span>
                <SelectDropdown
                  size="sm"
                  value={state}
                  onChange={(s) => setState(s as ResourceStatus)}
                  options={STATE_OPTIONS}
                  triggerClassName="w-32"
                />
              </div>
            )}
            {hasBackend && (
              <span className="flex items-center gap-1.5 text-[11.5px] text-mute">
                <span className="size-1.5 rounded-full bg-pos" />
                Connected
              </span>
            )}
            {role ? (
              <div className="flex items-center gap-2">
                <span
                  className="flex items-center gap-1.5 rounded-full border border-line bg-bg px-2.5 py-0.5 text-[11px] font-semibold text-ink"
                  aria-label={`Signed in as ${role}`}
                >
                  <span
                    className={`size-1.5 rounded-full ${
                      role === "manager" ? "bg-pos" : "bg-[#38bdf8]"
                    }`}
                  />
                  <span className="capitalize">{role}</span>
                </span>
                {onLogout && (
                  <button
                    onClick={onLogout}
                    title="Sign Out"
                    className="flex h-7 items-center rounded border border-line/60 bg-surface px-2 text-[11.5px] font-medium text-mute transition-colors hover:border-neg/30 hover:bg-neg/10 hover:text-neg"
                  >
                    Logout
                  </button>
                )}
              </div>
            ) : (
              !isLoginPage && (
                <Link
                  to="/login"
                  className="flex h-7 items-center rounded border border-line bg-surface px-2.5 text-[11.5px] font-semibold text-ink transition-colors hover:bg-line/40"
                >
                  Sign In
                </Link>
              )
            )}
          </div>
        </header>

        <main
          id="main"
          key={path}
          className="mx-auto w-full max-w-[1320px] flex-1 animate-fade px-4 py-6 lg:px-8 lg:py-8"
        >
          {children}
        </main>
      </div>
    </div>
  )
}
