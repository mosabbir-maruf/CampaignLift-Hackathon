# CampaignLift Frontend

Decision support workstation frontend for CampaignLift uplift modeling and campaign optimization.

## Getting Started

### Prerequisites
- Node.js >= 18
- pnpm >= 9

### Run Commands

Install dependencies:
```bash
pnpm install
```

Start the local development server:
```bash
pnpm dev
```
The application will be served at `http://localhost:5173`.

Type check and build for production:
```bash
pnpm run build
```

Preview the production build locally:
```bash
pnpm preview
```

## Workflow Routes

The interface implements the 9 canonical decision workflow steps:

1. **Overview** (`/`): High-level campaign decision summary and uplift vs. response orientation.
2. **Campaign Setup** (`/setup`): Scenario configuration, objective, offer parameters, and budget constraint input.
3. **Audience** (`/audience`): Individual customer uplift distribution, response probabilities (`p_treat`, `p_control`), and targeting status classification.
4. **Uplift Analysis** (`/uplift`): Diverging decile chart and treatment vs. control divergence.
5. **Strategy Comparison** (`/strategy`): Direct comparison of Random, Response-based, and Uplift targeting under identical budget constraints.
6. **Budget Optimization** (`/budget`): Knapsack budget allocation maximizing incremental conversions.
7. **Customer Explanation** (`/explain`): Feature contributions and grounded reason codes for individual customer recommendations.
8. **Experiment Intelligence** (`/experiment`): Factual trial evaluation comparing randomized treatment and control arms.
9. **Campaign Copilot** (`/copilot`): Grounded AI assistant answering questions from verified backend campaign run context.

## Design Philosophy & Guardrails
- **Presentation Layer Only**: Scoring, causal inference, and budget optimization are strictly handled by the backend API.
- **Metric Integrity**: No fabricated metrics or synthetic estimates presented as live truth. Data-not-loaded states render honestly when data is unpopulated.
- **Responsible AI**: Feature contributions explain model associations, not proven causal impact.
