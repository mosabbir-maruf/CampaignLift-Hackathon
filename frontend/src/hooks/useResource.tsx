import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { hasBackend } from "../api/client"

export type ResourceStatus = "loading" | "error" | "empty" | "insufficient" | "ready"

// Preview control so reviewers can inspect every designed state.
// In production this is ignored once real fetchers are wired.
const PreviewCtx = createContext<{
  state: ResourceStatus
  setState: (s: ResourceStatus) => void
}>({
  state: "ready",
  setState: () => {},
})

export function PreviewProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ResourceStatus>("ready")
  return (
    <PreviewCtx.Provider value={{ state, setState }}>
      {children}
    </PreviewCtx.Provider>
  )
}

export const usePreview = () => useContext(PreviewCtx)

/**
 * Loads a resource. With a backend configured, `fetcher` is used and its
 * errors surface as-is — failed requests are never replaced with demo data.
 * Without one, the illustrative fixture is shown under the preview state.
 */
export function useResource<T>(demo: T, fetcher?: () => Promise<T>) {
  const { state } = usePreview()
  const [status, setStatus] = useState<ResourceStatus>("loading")
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let alive = true
    setStatus("loading")
    if (hasBackend && fetcher) {
      fetcher()
        .then((d) => alive && (setData(d), setStatus("ready")))
        .catch((e: Error) => alive && (setError(e.message), setStatus("error")))
      return () => {
        alive = false
      }
    }
    const t = setTimeout(
      () => {
        if (!alive) return
        setData(state === "ready" ? demo : null)
        setError(
          state === "error"
            ? "The scoring service returned 503 Service Unavailable."
            : null,
        )
        setStatus(state)
      },
      state === "loading" ? 1e9 : 450,
    )
    return () => {
      alive = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, nonce])

  return {
    status,
    data,
    error,
    retry: () => setNonce((n) => n + 1),
    illustrative: !hasBackend,
  }
}
