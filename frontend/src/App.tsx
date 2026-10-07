import { useEffect, useState } from "react"
import AppShell from "./components/AppShell"
import { RouterProvider, useRoute, navigate } from "./lib/router"
import { PreviewProvider } from "./hooks/useResource"
import { getSession, logout as apiLogout, hasBackend } from "./api/client"
import Overview from "./pages/Overview"
import CampaignSetup from "./pages/CampaignSetup"
import Audience from "./pages/Audience"
import UpliftAnalysis from "./pages/UpliftAnalysis"
import StrategyComparison from "./pages/StrategyComparison"
import BudgetOptimization from "./pages/BudgetOptimization"
import CustomerExplanation from "./pages/CustomerExplanation"
import ExperimentIntelligence from "./pages/ExperimentIntelligence"
import CampaignCopilot from "./pages/CampaignCopilot"
import Login from "./pages/Login"

const ROUTE_TITLES: Record<string, string> = {
  "/login": "Sign In — CampaignLift",
  "/": "CampaignLift — Campaign Intelligence",
  "/setup": "Campaign Setup — CampaignLift",
  "/audience": "Audience Targeting — CampaignLift",
  "/uplift": "Uplift Analysis — CampaignLift",
  "/strategy": "Strategy Comparison — CampaignLift",
  "/budget": "Budget Optimization — CampaignLift",
  "/explain": "Customer Explanation — CampaignLift",
  "/experiment": "Experiment Intelligence — CampaignLift",
  "/copilot": "Campaign Copilot — CampaignLift",
}

const ROUTES: Record<string, React.ComponentType<any>> = {
  "/login": Login,
  "/": Overview,
  "/setup": CampaignSetup,
  "/audience": Audience,
  "/uplift": UpliftAnalysis,
  "/strategy": StrategyComparison,
  "/budget": BudgetOptimization,
  "/explain": CustomerExplanation,
  "/experiment": ExperimentIntelligence,
  "/copilot": CampaignCopilot,
}

function AppContent() {
  const { path } = useRoute()
  const [role, setRole] = useState<"manager" | "viewer" | null>(null)

  useEffect(() => {
    document.title = ROUTE_TITLES[path] ?? "CampaignLift"
  }, [path])

  useEffect(() => {
    if (!hasBackend) {
      setRole("manager")
      return
    }

    getSession()
      .then((res) => {
        if (res.authenticated && res.role) {
          setRole(res.role)
          if (path === "/login") {
            navigate("/")
          }
        } else {
          setRole(null)
          if (path !== "/login") {
            navigate("/login")
          }
        }
      })
      .catch(() => {
        setRole(null)
        if (path !== "/login") {
          navigate("/login")
        }
      })
  }, [path])

  const handleLogout = async () => {
    try {
      await apiLogout()
    } catch {
      // ignore
    }
    setRole(null)
    navigate("/login")
  }

  const handleLoginSuccess = (userRole: "manager" | "viewer") => {
    setRole(userRole)
    navigate("/")
  }

  const Page = ROUTES[path] ?? Overview

  return (
    <AppShell role={role} onLogout={handleLogout}>
      <Page onLoginSuccess={handleLoginSuccess} />
    </AppShell>
  )
}

export default function App() {
  return (
    <RouterProvider>
      <PreviewProvider>
        <AppContent />
      </PreviewProvider>
    </RouterProvider>
  )
}

