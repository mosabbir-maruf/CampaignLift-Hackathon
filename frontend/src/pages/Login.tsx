import { useState, type FormEvent } from "react"
import { login } from "../api/client"
import { navigate } from "../lib/router"

interface LoginProps {
  onLoginSuccess?: (role: "manager" | "viewer") => void
}

export default function Login({ onLoginSuccess }: LoginProps) {
  const [role, setRole] = useState<"manager" | "viewer">("manager")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!password) {
      setError("Please enter a password.")
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await login(role, password)
      if (res.status === "ok") {
        if (onLoginSuccess) {
          onLoginSuccess(res.role)
        }
        navigate("/")
      } else {
        setError("Invalid credentials. Please try again.")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed."
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[75vh] items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-8 shadow-2xl backdrop-blur-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-ink text-white">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-ink">
            Sign In to CampaignLift
          </h1>
          <p className="mt-1 text-[13px] text-mute">
            Select role and authenticate to access decision engine
          </p>
        </div>

        {/* Error banner */}
        {error && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-2.5 rounded-lg border border-neg/30 bg-neg/10 px-3.5 py-2.5 text-[12.5px] text-neg"
          >
            <span className="font-semibold">Error:</span>
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Role selector tabs */}
          <div>
            <label className="mb-2 block text-[12px] font-semibold tracking-wider text-mute uppercase">
              Select Role
            </label>
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-bg p-1 border border-line">
              <button
                type="button"
                onClick={() => setRole("manager")}
                className={`flex flex-col items-center justify-center rounded-md py-2 px-3 text-[13px] font-medium transition-all ${
                  role === "manager"
                    ? "bg-surface text-ink shadow-sm font-semibold"
                    : "text-mute hover:text-ink"
                }`}
              >
                <span>Campaign Manager</span>
                <span className="text-[10px] text-mute">Write & Optimize</span>
              </button>
              <button
                type="button"
                onClick={() => setRole("viewer")}
                className={`flex flex-col items-center justify-center rounded-md py-2 px-3 text-[13px] font-medium transition-all ${
                  role === "viewer"
                    ? "bg-surface text-ink shadow-sm font-semibold"
                    : "text-mute hover:text-ink"
                }`}
              >
                <span>Viewer</span>
                <span className="text-[10px] text-mute">Read-Only</span>
              </button>
            </div>
          </div>

          {/* Password field */}
          <div>
            <label
              htmlFor="password-input"
              className="mb-1.5 block text-[12px] font-semibold tracking-wider text-mute uppercase"
            >
              Password
            </label>
            <input
              id="password-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`Enter password for ${role}`}
              className="w-full rounded-lg border border-line bg-bg px-3.5 py-2.5 text-[13.5px] text-ink placeholder:text-mute/60 focus:border-[#2ED8A3] focus:outline-none focus:ring-1 focus:ring-[#2ED8A3]"
              required
            />
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 flex h-10 w-full items-center justify-center rounded-lg bg-[#1DB584] text-[13.5px] font-semibold text-white shadow-sm transition-all hover:bg-[#189b70] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Authenticating..." : `Sign In as ${role === "manager" ? "Manager" : "Viewer"}`}
          </button>
        </form>

        {/* Security context notice */}
        <div className="mt-6 border-t border-line/60 pt-4 text-center">
          <p className="text-[11px] text-mute/80">
            Role-Based Access Control enforced via HttpOnly session cookies.
            <br />
            No credentials stored in frontend state.
          </p>
        </div>
      </div>
    </div>
  )
}
