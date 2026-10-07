# CampaignLift Backend Service

FastAPI causal inference, campaign optimization, and decision intelligence engine.

<p align="left">
  <a href="https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-backend">
    <img src="https://img.shields.io/badge/Docker-backend--image-2496ed.svg?logo=docker&logoColor=white" alt="Docker Backend Image" />
  </a>
  <a href="https://www.python.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white" alt="Python 3.11" />
  </a>
  <a href="https://fastapi.tiangolo.com/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI" />
  </a>
  <a href="https://lightgbm.readthedocs.io/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/ML-LightGBM-brightgreen.svg" alt="LightGBM" />
  </a>
  <a href="https://www.sqlite.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Database-SQLite-003B57.svg?logo=sqlite&logoColor=white" alt="SQLite" />
  </a>
  <a href="https://docs.pytest.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Tests-pytest-0a9edc.svg?logo=pytest&logoColor=white" alt="pytest" />
  </a>
  <a href="../LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
  </a>
</p>

---

## Overview

The CampaignLift backend is a production-grade Python service built on **FastAPI** that powers the causal decision intelligence pipeline for Mobile Financial Services (MFS) marketing campaigns:

- **Causal Uplift Inference**: Computes individual counterfactual treatment effects $\tau(X) = P(\text{transact} \mid X, 1) - P(\text{transact} \mid X, 0)$ using pre-trained LightGBM S-Learner models with treatment interaction features.
- **Greedy Knapsack Budget Optimizer**: Allocates marketing budget dynamically to maximize incremental transaction volume while strictly eliminating negative-uplift segments ("Sleeping Dogs").
- **Customer Explainability**: Computes deterministic feature attributions and assigns human-interpretable reason codes (`incremental_candidate`, `likely_without_offer`, `weak_response`, `negative_uplift`).
- **Experiment Intelligence**: Evaluates randomized trial performance across 23 customer segments, enforcing strict 30/30 sample support thresholds before reporting estimates.
- **Grounded Copilot Engine**: Integrates Google Gemini (`gemini-2.5-flash`), strictly bounded to verified run JSON context to prevent metric hallucination.
- **Stateless & Containerized**: Deployed as a multi-arch container (`linux/amd64`, `linux/arm64`) listening internally on port 8000 behind the Nginx reverse proxy.

---

## Directory Structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── __init__.py          # API route registry
│   │   │   └── campaigns.py         # Campaign scenario, scoring, optimization & explanation routes
│   │   └── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── inference.py             # Causal uplift scoring & LightGBM model artifact loader
│   │   ├── optimizer.py             # Knapsack budget optimizer & strategy comparison engine
│   │   ├── explain.py               # Customer-level feature attribution & reason code generator
│   │   ├── experiment.py            # Randomized trial evaluation with sample support guards
│   │   └── gemini.py                # Bounded Google Gemini copilot client & prompt builder
│   ├── db.py                        # SQLite schema initialization and connection management
│   ├── experiment.py                # Experiment trial analysis service adapter
│   ├── explain.py                   # Explanation service adapter
│   ├── gemini.py                    # Gemini copilot adapter
│   ├── inference.py                 # Inference service adapter
│   ├── main.py                      # FastAPI application factory, middleware, and health probes
│   ├── optimizer.py                 # Optimizer service adapter
│   ├── routes.py                    # Consolidated route handlers
│   ├── schemas.py                   # Pydantic request/response validation models
│   ├── settings.py                  # Environment settings loaded via pydantic-settings
│   └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_health.py               # /health and /ready probe test suite
│   ├── test_inference.py            # Model loading and uplift prediction tests
│   ├── test_optimizer.py            # Knapsack optimization and strategy comparison tests
│   ├── test_explain.py              # Attribution math and reason code tests
│   ├── test_experiment.py           # 30/30 sample support rule and trial analysis tests
│   └── test_gemini.py               # Bounded copilot context and grounding tests
├── Dockerfile                       # Multi-stage production container build (Python 3.11 slim)
├── requirements.txt                 # Pinned Python package dependencies
├── openapi.yaml                     # OpenAPI 3.1 REST API specification
└── README.md                        # Subsystem documentation
```

---

## Core Services & Architecture

### 1. Causal Uplift Inference (`services/inference.py`)
Loads pre-trained LightGBM S-Learner artifacts from `MODEL_ARTIFACT_DIR`. For each customer feature vector $X$, the service evaluates:
$$P(\text{transact} \mid X, \text{offer}=1) \quad \text{and} \quad P(\text{transact} \mid X, \text{offer}=0)$$
The difference yields the individual causal treatment effect:
$$\tau(X) = P(\text{transact} \mid X, 1) - P(\text{transact} \mid X, 0)$$
Customers are ranked into deciles to produce cumulative gain and Qini / AUUC curves.

### 2. Knapsack Budget Optimizer (`services/optimizer.py`)
Implements a greedy fractional/0-1 knapsack optimizer. Customers are evaluated by incremental efficiency:
$$\text{Efficiency}_i = \frac{\tau_i}{\text{Unit Cost}}$$
The optimizer strictly filters out all customers with $\tau_i \le 0$ ("Sleeping Dogs" and non-responders) and selects top candidates until the budget is exhausted, guaranteeing maximum incremental transactions per budget spent.

### 3. Customer Explainability (`services/explain.py`)
Provides transparent, deterministic feature attribution comparing the customer's top contributing attributes against cohort baselines. Generates four mutually exclusive reason codes:
- `incremental_candidate`: High positive uplift, low baseline propensity.
- `likely_without_offer`: High baseline propensity; offer subsidizes organic transaction.
- `weak_response`: Low baseline propensity with negligible offer sensitivity.
- `negative_uplift`: Treatment fatigue where offer decreases transaction likelihood.

### 4. Experiment Intelligence (`services/experiment.py`)
Analyzes simulated randomized trials across 23 customer segments. Enforces a **strict 30/30 sample support threshold**: if either the treatment or control arm has fewer than 30 observed customers in a slice, the system reports `insufficient_support` rather than misleading noisy estimates.

### 5. Grounded Campaign Copilot (`services/gemini.py`)
Interfaces with Google Gemini (`gemini-2.5-flash`). To prevent hallucination, the prompt injects the verified run context JSON and enforces system constraints: the model must cite exact values from the run context and refuse to invent unsubstantiated metrics or ROI claims.

---

## REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Container liveness probe (returns `{"status": "ok"}`) |
| `GET` | `/ready` | Container readiness probe (verifies DB & model artifact availability) |
| `POST` | `/api/campaigns` | Create and register a new campaign scenario |
| `GET` | `/api/campaigns/{id}` | Retrieve campaign scenario definition and status |
| `POST` | `/api/campaigns/{id}/score` | Execute causal uplift scoring for a campaign cohort |
| `GET` | `/api/campaigns/{id}/scores` | Retrieve customer-level uplift scores and decile distribution |
| `POST` | `/api/campaigns/{id}/optimize` | Run knapsack budget optimization across targeting strategies |
| `GET` | `/api/customers/{id}/explanation` | Fetch feature attribution and reason codes for an individual customer |
| `GET` | `/api/experiments/{id}/analysis` | Retrieve randomized trial evaluation with 30/30 sample support checks |
| `POST` | `/api/copilot/query` | Ask the grounded Gemini decision assistant about run results |

---

## Configuration & Environment Variables

The backend loads configuration from environment variables or the root `.env` file:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | string | `production` | Application environment (`local`, `production`) |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | string | `sqlite:////app/db/campaignlift.db` | SQLite database file connection URI |
| `MODEL_ARTIFACT_DIR` | path | `artifacts/models/...` | Path to pre-trained LightGBM model artifact directory |
| `FEATURE_TABLE_PATH` | path | `data/fixtures/fixture_v1/features.json` | Path to customer cohort feature table fixture |
| `DATASET_VERSION` | string | `cl-synth-ml_dev-20261006-8ad556a` | Version identifier for synthetic MFS data |
| `GEMINI_API_KEY` | string | `""` | Google Gemini API key for copilot integration |
| `GEMINI_MODEL` | string | `gemini-2.5-flash` | Gemini model identifier |

---

## Local Development & Testing

### 1. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install ruff mypy pytest
```

### 2. Run the Development Server
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 3. Run the Automated Test Suite
```bash
pytest backend/tests/ -v
```

### 4. Code Quality & Type Checking
```bash
# Linting
ruff check backend/app

# Type checking
mypy backend/app --ignore-missing-imports --explicit-package-bases
```

---

## Docker & Container Deployment

### Build Container Image
```bash
docker build -t campaignlift-backend -f backend/Dockerfile .
```

### Run Container Standalone
```bash
docker run -d \
  --name campaignlift-backend \
  -p 8000:8000 \
  -e APP_ENV=production \
  -e GEMINI_API_KEY="your-gemini-key" \
  ghcr.io/mosabbir-maruf/campaignlift-backend:latest
```
