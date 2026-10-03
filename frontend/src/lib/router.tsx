import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"

// Minimal hash router. Swap for react-router during integration if preferred.
interface Route {
  path: string
  query: URLSearchParams
}

const parse = (): Route => {
  const raw = window.location.hash.replace(/^#/, "") || "/"
  const [path, qs] = raw.split("?")
  return { path: path || "/", query: new URLSearchParams(qs) }
}

const RouterCtx = createContext<Route>({
  path: "/",
  query: new URLSearchParams(),
})

export function navigate(to: string) {
  window.location.hash = to
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const on = () => {
      setRoute(parse())
      document.getElementById("main")?.scrollTo({ top: 0 })
    }
    window.addEventListener("hashchange", on)
    return () => window.removeEventListener("hashchange", on)
  }, [])
  return <RouterCtx.Provider value={route}>{children}</RouterCtx.Provider>
}

export const useRoute = () => useContext(RouterCtx)

export function Link({
  to,
  className,
  children,
  ...rest
}: {
  to: string
  className?: string
  children: ReactNode
} & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={`#${to}`} className={className} {...rest}>
      {children}
    </a>
  )
}
