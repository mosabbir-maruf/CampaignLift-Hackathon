# CampaignLift System Architecture

CampaignLift is an AI-powered causal decision-support engine engineered specifically for Mobile Financial Services (MFS) marketing campaign teams. It shifts campaign targeting from response probability (who is likely to transact) to incremental uplift (who transacts *because* of an incentive).

---

## 1. High-Level Architectural Topology

The system is deployed as an isolated, containerized stack composed of an Nginx edge proxy and a modular FastAPI decision backend, backed by SQLite persistent storage.

```
Internet / User Browser
       │
       ▼  (Port 80 HTTP)
┌─────────────────────────────────────────────────────────────┐
│  frontend (Nginx Alpine Reverse Proxy & Static Host)        │
│  • Serves React 19 / TypeScript SPA assets                  │
│  • Gzip compression & immutable asset caching               │
│  • Proxy pass /health  ───► http://backend:8000/health      │
│  • Proxy pass /ready   ───► http://backend:8000/ready       │
│  • Proxy pass /api/*   ───► http://backend:8000/api/*       │
└──────────────────────────────┬──────────────────────────────┘
                               │  Private Docker Bridge Network
                               │  (Port 8000 NOT exposed externally)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  backend (FastAPI / Python 3.11 Decision Engine)            │
│  • Liveness & Readiness lifecycle probes                    │
│  • In-memory cached LightGBM S-Learner uplift model         │
│  • Pre-computed customer feature table caches               │
│  • Greedy Budget Optimization engine                        │
│  • Deterministic Customer Feature Attribution & Reason Codes│
│  • Grounded Gemini Copilot (advisory decision-support)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  campaignlift-db (Named Docker Volume)                      │
│  • Persistent SQLite relational database (/app/db)          │
│  • Campaign definitions, scored runs, and allocations       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### A. Frontend Workstation (`frontend/`)
- **Technology**: React 19, TypeScript 5.7, Vite 8, Tailwind CSS v4.
- **Role**: Presentation-layer decision-support workstation for campaign managers.
- **Screens**:
  1. *Analytics Workstation Overview*: Top-line portfolio summary and recent scenario runs.
  2. *Campaign Setup*: Form for objective, offer type, incentive unit cost, and total budget constraints.
  3. *Audience Explorer*: Searchable customer table with uplift scores, deciles, and eligibility flags.
  4. *Uplift Analysis*: SVG Decile Distribution charts visualizing treatment vs. control conversion rates.
  5. *Strategy Comparison*: Multi-strategy decision matrix (Random vs. Response vs. Uplift).
  6. *Budget Optimization*: Budget allocation curves with automatic negative-uplift exclusion.
  7. *Customer Explanation*: Feature attribution waterfall and reason codes for individual customer scores.
  8. *Campaign Copilot*: Grounded natural language assistant answering questions strictly from run JSON.

### B. Decision Engine Backend (`backend/`)
- **Technology**: FastAPI, Pydantic v2, Uvicorn, Python 3.11.
- **Service Modules**:
  - `inference.py`: Loads the model artifact and calculates $P(\text{treat})$, $P(\text{control})$, and uplift $\tau = P(\text{treat}) - P(\text{control})$.
  - `optimizer.py`: Sorts eligible customers by incremental value or uplift and allocates budget greedily, barring negative uplift cohorts.
  - `explain.py`: Computes directional feature contributions and maps predictions to deterministic reason codes (`incremental_candidate`, `likely_without_offer`, `weak_response`, `negative_uplift`).
  - `experiment.py`: Evaluates trial arms on factual cohort data and enforces the 30/30 minimum randomized support rule across slices.
  - `gemini.py`: Interfaces with Google Gemini (default `gemini-2.5-flash`), locking system instructions to prevent hallucinations or prompt injection.

### C. Machine Learning Engine (`ml/`)
- **Production Model**: LightGBM S-Learner with treatment interaction terms.
- **Artifact Layout**:
  - `model.joblib`: Trained scikit-learn / LightGBM pipeline.
  - `metadata.json`: Model version, training parameters, seed, git commit, and validation metrics.
  - `feature_list.json`: Strict schema of required categorical and numeric features.
  - `test_metrics.json` & `validation_metrics.json`: Measured Qini, AUUC, and top-decile lift.

### D. Synthetic Data Generator (`data/`)
- **Role**: Reproducible data synthesis generating realistic MFS histories (transactions, merchant categories, prior campaign fatigue, and randomized treatment assignment) without leaking ground-truth causal mechanisms.

---

## 3. Security & Operational Boundaries

1. **Strictly Decision Support**: The interface is advisory. There is no automated campaign dispatch, SMS trigger, or money transfer execution.
2. **Reverse Proxy Isolation**: Only port 80 (HTTP) is published on the host. The backend ASGI server binds exclusively to the private Docker bridge network.
3. **Container Hardening**: Backend runs as a dedicated non-root user (`appuser`, UID 1000).
4. **Secret Management**: Runtime keys (`GEMINI_API_KEY`) are read strictly from environment variables and never baked into container layers or logged.
