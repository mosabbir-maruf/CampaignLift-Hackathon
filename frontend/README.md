# CampaignLift Workstation Frontend

React 19 decision support workstation for causal uplift modeling and campaign optimization.

<p align="left">
  <a href="https://devtree.online/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Live_Demo-devtree.online-2ea44f.svg?logo=cloudflare&logoColor=white" alt="Live Demo" />
  </a>
  <a href="https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-frontend">
    <img src="https://img.shields.io/badge/Docker-frontend--image-2496ed.svg?logo=docker&logoColor=white" alt="Docker Frontend Image" />
  </a>
  <a href="https://react.dev/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/React-19-61dafb.svg?logo=react&logoColor=black" alt="React 19" />
  </a>
  <a href="https://www.typescriptlang.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/TypeScript-5.7-3178c6.svg?logo=typescript&logoColor=white" alt="TypeScript 5.7" />
  </a>
  <a href="https://vite.dev/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Vite-8-646cff.svg?logo=vite&logoColor=white" alt="Vite 8" />
  </a>
  <a href="https://tailwindcss.com/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Tailwind_CSS-v4-38bdf8.svg?logo=tailwindcss&logoColor=white" alt="Tailwind CSS v4" />
  </a>
  <a href="../LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
  </a>
</p>

---

## Overview

The CampaignLift frontend is a high-density, editorial decision support workstation designed for retention, marketing, and growth teams in Mobile Financial Services (MFS).

- **Strict Frontend/Backend Boundary**: The UI is strictly a presentation and interaction layer. All causal inference, LightGBM scoring, and knapsack optimization are executed exclusively by the backend API.
- **Metric Integrity**: Zero synthetic estimates or placeholder values are disguised as ground truth. Empty and insufficient support states render with clear diagnostic feedback.
- **Responsible AI Guardrails**: Model attributions are explicitly framed as descriptive feature associations, not unproven causal claims.
- **Production Ingress**: Packaged in a lightweight Alpine Nginx container that provides static asset caching, SPA routing, API reverse proxying, and HTTPS TLS termination via Cloudflare Origin Certificates.
- **Live Deployment**: Hosted in production on AWS EC2 at [https://devtree.online/](https://devtree.online/).

---

## Directory Structure

```text
frontend/
├── public/
│   ├── favicon.svg                  # Vector application favicon
│   ├── favicon.ico                  # Fallback ICO favicon
│   ├── favicon-16x16.png            # 16x16 PNG favicon
│   ├── favicon-32x32.png            # 32x32 PNG favicon
│   ├── apple-touch-icon.png         # iOS touch icon
│   ├── logo.png                     # Official CampaignLift high-res brand logo
│   └── opengraph.webp               # Social preview and decision platform banner
├── src/
│   ├── api/
│   │   ├── client.ts                # Typed fetch client connecting to /api/* endpoints
│   │   ├── types.ts                 # Full TypeScript domain contracts matching FastAPI schemas
│   │   └── demo.ts                  # Illustrative fallback fixtures for preview states
│   ├── components/
│   │   ├── AppShell.tsx             # Master workstation layout (responsive sidebar, topbar, content)
│   │   ├── DataTable.tsx            # High-density sortable tabular views with pagination
│   │   ├── DecileChart.tsx          # Diverging treatment vs. control decile SVG visualization
│   │   ├── Composition.tsx          # Segment composition breakdown and cohort badges
│   │   └── ui.tsx                   # Design system primitives (cards, buttons, alerts, drawers)
│   ├── hooks/
│   │   └── useResource.tsx          # Asynchronous data loading hook with state switches
│   ├── lib/
│   │   ├── campaign.ts              # Campaign state helpers and scenario utilities
│   │   ├── format.ts                # Currency, percentage, uplift delta, and number formatters
│   │   └── router.tsx               # Client-side hash/path router with history support
│   ├── pages/
│   │   ├── Overview.tsx             # Step 01: Decision summary and uplift vs. propensity orientation
│   │   ├── CampaignSetup.tsx        # Step 02: Scenario definition, offer types, and budget input
│   │   ├── Audience.tsx             # Step 03: Customer cohort uplift scoring and probability tables
│   │   ├── UpliftAnalysis.tsx       # Step 04: Decile distribution, cumulative gains, and Qini curves
│   │   ├── StrategyComparison.tsx   # Step 05: Side-by-side comparison of targeting strategies
│   │   ├── BudgetOptimization.tsx   # Step 06: Knapsack budget optimizer and customer allocations
│   │   ├── CustomerExplanation.tsx  # Step 07: Individual customer waterfall attribution & reason codes
│   │   ├── ExperimentIntelligence.tsx # Step 08: Randomized trial evaluation with 30/30 sample support
│   │   └── CampaignCopilot.tsx      # Step 09: Grounded Gemini decision support conversation interface
│   ├── App.tsx                      # Root component orchestrating routing and state persistence
│   ├── index.css                    # Design tokens, typography rules, and Tailwind CSS v4 directives
│   ├── main.tsx                     # React 19 entry point mounting root App
│   └── vite-env.d.ts                # Vite environment variable type declarations
├── Dockerfile                       # Multi-stage production container build (Node 22 -> Alpine Nginx)
├── nginx.conf                       # Nginx HTTP-to-HTTPS redirect, SSL termination & reverse proxy
├── package.json                     # Project scripts and dependency declarations
├── pnpm-lock.yaml                   # Pinned pnpm lockfile
├── tsconfig.json                    # TypeScript compiler configuration (strict mode)
├── vite.config.ts                   # Vite 8 bundler configuration with React and Tailwind v4 plugins
├── AGENTS.md                        # Development guardrails and workstation design constraints
└── README.md                        # Subsystem documentation
```

---

## The 9 Workflow Routes

| Step | Route | Name | Focus & Functionality |
| :---: | :--- | :--- | :--- |
| **01** | `/` | **Overview** | Orientation on why uplift modeling supersedes propensity modeling; executive KPI cards. |
| **02** | `/setup` | **Campaign Setup** | Form to configure campaign name, objective, offer mechanism (cashback, waiver, discount), and total budget. |
| **03** | `/audience` | **Audience Explorer** | Customer cohort table displaying individual treatment probabilities ($P_{\text{treat}}, P_{\text{control}}$) and uplift rank. |
| **04** | `/uplift` | **Uplift Analysis** | Decile divergence SVG charts, cumulative gains, and Qini / AUUC performance evaluation. |
| **05** | `/strategy` | **Strategy Comparison** | Side-by-side comparison matrix evaluating Random, Propensity, and Uplift targeting under fixed spend. |
| **06** | `/budget` | **Budget Optimization** | Greedy knapsack budget allocation maximizing incremental transaction count while filtering non-responders. |
| **07** | `/explain` | **Customer Explanation** | Drawer inspecting individual customer feature contributions and transparent reason codes. |
| **08** | `/experiment` | **Experiment Intelligence**| Simulated A/B trial evaluation with strict 30/30 minimum sample support guards per segment. |
| **09** | `/copilot` | **Campaign Copilot** | Server-side Gemini assistant strictly grounded to verified run JSON context without hallucinations. |

---

## Design System & Workstation Aesthetics

The application avoids standard consumer SaaS templates in favor of a specialized **editorial analytics workstation**:
- **Paper Surface**: Canvas background uses warm parchment tone (`#f3f3f0` / `#fafaf8`) paired with crisp hairline borders (`1px solid #e5e5e0`).
- **Typography Hierarchy**: Primary headers in **Inter Tight** paired with monospace numerical metrics in **JetBrains Mono**.
- **Semantic Directional Uplift**:
  - Positive Uplift: Emerald / Forest Green (`▲ +X.XX%`)
  - Negative Uplift: Vermilion / Brick Red (`▼ -X.XX%`)
  - Insufficient Support: Amber (`◆ Insufficient sample support`)
  - Baseline / Neutral: Slate (`—`)
- **Responsive Navigation**: Full collapsible sidebar on desktop, compact icon rail on tablet, sliding drawer on mobile.

---

## Local Development

### 1. Prerequisites
- **Node.js**: >= 20.x (Node 22 recommended)
- **pnpm**: >= 9.x (`corepack enable && corepack prepare pnpm@latest --activate`)

### 2. Install Dependencies
```bash
pnpm install
```

### 3. Start Local Development Server
```bash
pnpm dev
```
The workstation will be available locally at `http://localhost:5173`. By default, it proxies `/api/*` to the FastAPI backend at `http://localhost:8000`.

### 4. Code Quality & Type Checking
```bash
# TypeScript compiler typecheck (0 errors required)
pnpm run typecheck

# Code formatting & style verification via oxfmt
pnpm run lint

# Auto-format codebase
pnpm run format
```

### 5. Build for Production
```bash
pnpm run build
```
Generates optimized static client assets in `dist/`.

### 6. Preview Production Bundle Locally
```bash
pnpm preview
```

---

## Docker & Production Nginx Setup

The frontend container is built using a two-stage Dockerfile:
1. **Build Stage**: Node 22 Alpine runs `pnpm build` to compile TypeScript into static assets.
2. **Runtime Stage**: Nginx Alpine serves static files and reverse proxies API requests.

### Key Nginx Proxy Rules (`nginx.conf`)
- **Port 80**: Automatically redirects standard HTTP traffic to HTTPS via a `301 Moved Permanently`.
- **Port 443**: Terminates TLS using Cloudflare Origin Certificates mounted at `/etc/nginx/certs/origin.pem` and `/etc/nginx/certs/origin.key`.
- **Reverse Proxy**: Proxies `/api/` to `http://api:8000/api/` with streaming and buffer headers preserved.
- **Health Probes**: Direct pass-through for `/health` and `/ready` probes.
- **SPA Fallback**: `try_files $uri $uri/ /index.html` ensuring client-side routes resolve without 404s.

### Run Production Image Standalone
```bash
docker run -d \
  --name campaignlift-frontend \
  -p 80:80 \
  -p 443:443 \
  -v /home/ubuntu/campaignlift/certs:/etc/nginx/certs:ro \
  ghcr.io/mosabbir-maruf/campaignlift-frontend:latest
```
