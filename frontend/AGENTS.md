# CampaignLift Frontend

React + Vite + TypeScript + Tailwind CSS frontend for CampaignLift.

## Project Purpose
CampaignLift is an uplift-modeling decision support application designed for retention and marketing teams to prioritize interventions, optimize campaign budgets, compare treatment strategies, and inspect customer-level uplift predictions.

## Tech Stack
- **Framework & Runtime**: React 19, React DOM 19
- **Build Tooling & Language**: Vite 8, TypeScript 5.7
- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite`
- **Formatting**: oxfmt
- **Package Manager**: pnpm

## Development Commands
- `pnpm dev`: Start Vite development server
- `pnpm build`: Run type checks and build for production
- `pnpm preview`: Preview production build locally
- `pnpm format`: Format codebase using oxfmt

## Project Structure
- `index.html`: Application entry HTML shell
- `vite.config.ts`: Vite bundler configuration with React and Tailwind v4 plugins
- `src/main.tsx`: Application bootstrap mounting `src/App.tsx`
- `src/App.tsx`: Main application router and shell container
- `src/index.css`: Global styles, design tokens, and Tailwind v4 import
- `src/pages/`: The 9 workflow pages (Overview, CampaignSetup, Audience, UpliftAnalysis, StrategyComparison, BudgetOptimization, CustomerExplanation, ExperimentIntelligence, CampaignCopilot)
- `src/components/`: Reusable UI elements, AppShell, Sidebar, Topbar, DataTables, and state views
- `src/api/`: Typed API client (`client.ts`), data types (`types.ts`), and illustrative fixtures (`demo.ts`)
- `src/hooks/`: UI hooks including `useResource` and preview state switches
- `src/lib/`: Application utilities and client-side routing

## Frontend/Backend Separation
- The frontend is strictly a presentation and interaction layer.
- All machine learning, scoring, causal inference, and optimization calculations are executed by the backend.
- Do not run client-side statistical estimation or modeling algorithms.

## API Integration Rule
- Wire network operations through `src/api/client.ts` using `import.meta.env.VITE_API_BASE_URL`.
- Use the existing API contract (`src/api/types.ts`). Do not invent undocumented endpoints or alter contracts unilaterally.

## Security & Secrets
- Never store API keys, tokens, or credentials in the frontend codebase or environment variables.
- All authenticated operations must be handled securely through backend session cookies or proxy mechanisms.

## Integrity of Metrics & Experimentation
- **No Fabricated Metrics**: Never display synthetic data as live ground truth. Demo data must remain clearly labeled as illustrative.
- **No Fabricated Experiment Results**: If test data is missing or incomplete, display "Not available" or the empty/insufficient state rather than placeholder numbers.
- **No Causal Claims from Model Explanations**: Feature contributions explain model output associations, not proven causal impact. Disclaimers must accompany explanation views.

## Design & UX Rules
- Maintain the editorial analytics workstation aesthetic: paper surface (`#f3f3f0`), crisp typography (Inter Tight, JetBrains Mono), hairline borders, and dense tables.
- Use semantic colors strictly: positive uplift (green), negative uplift (vermilion), insufficient support (amber), and neutral (slate).
- Always pair uplift metrics with signs and directional glyphs (▲, ▼, ◆).
- Support responsive viewport breakpoints (full sidebar at desktop, rail at tablet, drawer on mobile).

## Validation Expectations
- All changes must pass `pnpm build` without TypeScript errors or build warnings.
- Components must be exported as default exports and maintain balanced JSX.
- Verify clean rendering across all application states (loading, empty, ready, error, insufficient support).
