import { useEffect } from "react"
import AppShell from "./components/AppShell"
import { RouterProvider, useRoute } from "./lib/router"
import { PreviewProvider } from "./hooks/useResource"
import Overview from "./pages/Overview"
import CampaignSetup from "./pages/CampaignSetup"
import Audience from "./pages/Audience"
import UpliftAnalysis from "./pages/UpliftAnalysis"
import StrategyComparison from "./pages/StrategyComparison"
import BudgetOptimization from "./pages/BudgetOptimization"
import CustomerExplanation from "./pages/CustomerExplanation"
import ExperimentIntelligence from "./pages/ExperimentIntelligence"
import CampaignCopilot from "./pages/CampaignCopilot"

const ROUTE_TITLES: Record<string, string> = {
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

const ROUTES: Record<string, () => React.JSX.Element> = {
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

function Routes() {
  const { path } = useRoute()

  useEffect(() => {
    document.title = ROUTE_TITLES[path] ?? "CampaignLift"
  }, [path])

  const Page = ROUTES[path] ?? Overview
  return <Page />
}

export default function App() {
  return (
    <RouterProvider>
      <PreviewProvider>
        <AppShell>
          <Routes />
        </AppShell>
      </PreviewProvider>
    </RouterProvider>
  )
}
