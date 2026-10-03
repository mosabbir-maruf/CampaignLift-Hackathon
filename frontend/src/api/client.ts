// Thin, typed HTTP helper. No endpoints are defined here on purpose:
// the engineering team wires real paths from the FastAPI contract.
// Never put API keys in this file — Copilot/LLM calls go through the backend.

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined

export const hasBackend = Boolean(BASE_URL)

export async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!BASE_URL) throw new Error("VITE_API_BASE_URL is not configured")
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json() as Promise<T>
}
