# CampaignLift — AI-Powered Incremental Campaign Decision Engine for MFS

**Track**: Track 04 — Growth & Campaign Intelligence  
**Challenge**: AI DEV FEST 2026 AI Hackathon  
**Team Members**: Assaduzzaman, Mosabbir Maruf, Anik  

---

## 1. Problem, Solution & Purpose

### The Problem
Mobile Financial Services (MFS) spend heavily on promotional incentives (cashback, transaction fee waivers, coupon discounts). However, conventional marketing automation targets customers based on **Response Propensity** ($P(\text{transact} \mid \text{offer})$). This leads to severe budget waste:
- **Incentive Cannibalization**: Upwards of 40% of campaign spend subsidizes "Sure Things"—highly engaged customers who would have completed the transaction organically.
- **Customer Fatigue**: Badgering dormant or sensitive segments often triggers negative treatment reactions ("Sleeping Dogs"), accelerating churn.

### The Solution
CampaignLift reformulates campaign audience selection from a propensity problem into an **Incremental Causal Uplift** problem:
$$\tau(X) = P(\text{transact} \mid X, \text{offer}) - P(\text{transact} \mid X, \text{no offer})$$

By directly estimating the incremental uplift $\tau(X)$, CampaignLift isolates the true **"Persuadables"** from the "Sure Things" and "Sleeping Dogs", optimizing marketing return on investment and protecting customer relationships.

---

## 2. Key Features & How AI is Used

1. **Causal Uplift Inference**: Production-grade LightGBM S-Learner with treatment interaction terms, providing counterfactual probability estimates ($P(\text{treat})$ vs $P(\text{control})$).
2. **Greedy Knapsack Budget Optimizer**: Allocates budget dynamically to maximize total incremental transaction volume while strictly filtering out negative-uplift segments.
3. **Strategy Comparison Matrix**: Side-by-side decision matrix demonstrating the commercial divergence between Random, Response, and Uplift targeting.
4. **Deterministic Feature Attribution & Reason Codes**: Explainability engine providing linear feature contributions and plain-language reason codes (`incremental_candidate`, `likely_without_offer`, `weak_response`, `negative_uplift`).
5. **Grounded Gemini Copilot**: AI decision-support assistant using **Google Gemini (`gemini-2.5-flash`)**, strictly bounded by system instructions to answer exclusively from verified run context JSON and reject prompt injections.
6. **Experiment Intelligence**: Simulated trial analysis evaluating treatment vs. control arms with strict 30/30 sample support thresholds across 23 demographic and behavioral slices.

---

## 3. Technology Stack

- **Machine Learning**: LightGBM 4.7, scikit-learn 1.9, pandas 3.0, numpy 2.4, joblib.
- **Backend API**: Python 3.11, FastAPI, Pydantic v2, Uvicorn, SQLite.
- **LLM Integration**: Google Gemini (`gemini-2.5-flash`), server-side only via Google GenAI SDK / HTTP client.
- **Frontend Workstation**: React 19, TypeScript 5.7, Vite 8, Tailwind CSS v4, Lucide React.
- **Containerization & Edge**: Docker, Docker Compose v2, Nginx Alpine (reverse proxy, gzip compression, asset caching).
- **CI/CD Pipeline**: GitHub Actions with multi-platform builds (`linux/amd64`, `linux/arm64`) and automated GHCR package retention.

---

## 4. Live URL & Deployment Status

- **Local Deployment**: Fully containerized and verified locally at `http://localhost` via Docker Compose.
- **Cloud Hosting Status**: Cloud AWS EC2 host deployment is actively in progress by teammate Mosabbir (Step 25).
- **Liveness & Readiness**:
  - `GET http://localhost/health` -> `200 OK` (`{"status": "ok"}`)
  - `GET http://localhost/ready` -> `200 OK` (`{"status": "ready", "model_loaded": true, ...}`)

---

## 5. Prerequisites & Quickstart

### Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- (Optional for local development) Python 3.11+ and Node.js v22+

### 1. Clone & Configure
```bash
git clone https://github.com/mosabbir-maruf/CampaignLift-Internal.git
cd CampaignLift-Internal

# Copy canonical environment template
cp .env.example .env
```

### 2. Launch with Docker Compose
```bash
# Build and run containers locally
docker compose up --build -d

# Check service health
docker compose ps
curl http://localhost/ready
```

Access the Analytics Workstation at **`http://localhost`**.

---

## 6. Environment Configuration

All settings are configured through `.env` (never commit `.env` to version control):

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `PORT` | Public HTTP port exposed on the host | `80` |
| `APP_ENV` | Application environment (`local`, `production`) | `production` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `DATABASE_URL` | SQLite database URI inside container volume | `sqlite:////app/db/campaignlift.db` |
| `MODEL_ARTIFACT_DIR` | Relative path to pre-packaged model directory | `artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01` |
| `FEATURE_TABLE_PATH` | Pre-computed customer feature table JSON | `data/fixtures/fixture_v1/features.json` |
| `DATASET_VERSION` | Active dataset version identifier | `cl-synth-ml_dev-20261006-8ad556a` |
| `GEMINI_API_KEY` | Optional Google Gemini API key for Copilot | `""` (Optional; returns graceful 503 if omitted) |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-2.5-flash` |
| `FRONTEND_IMAGE` | Container registry image for frontend | `ghcr.io/<owner>/campaignlift-frontend:latest` |
| `BACKEND_IMAGE` | Container registry image for backend | `ghcr.io/<owner>/campaignlift-backend:latest` |

---

## 7. Testing & Verification

Run the full automated test suite locally:

```bash
# 1. Backend tests (50 tests: health, readiness, inference, optimizer, explain, copilot)
pytest backend/tests/ -v

# 2. Synthetic data engine & leakage tests (58 tests: schemas, temporal cutoffs, anti-leakage)
pytest data/tests/ -v

# 3. Machine learning candidates & metrics (75 tests: baseline, learners, Qini, AUUC)
pytest ml/tests/ -v -o pythonpath=". ml/src data/src"

# 4. Frontend static typecheck & bundle build
cd frontend
npm run typecheck
npx vite build
```

---

## 8. Public Documentation Map

Comprehensive project documentation is organized in [`docs/`](docs/):

- [`docs/architecture.md`](docs/architecture.md): Container topology, reverse proxy isolation, and component boundaries.
- [`docs/ml_methodology.md`](docs/ml_methodology.md): Uplift framing, anti-leakage rules, and measured Qini/AUUC evaluation metrics.
- [`docs/api.md`](docs/api.md): RESTful endpoint specifications, payloads, and response structures.
- [`docs/deployment.md`](docs/deployment.md): Docker Compose setup and cloud AWS EC2 configuration.
- [`docs/reproducibility.md`](docs/reproducibility.md): Fixed seeds, dataset release manifests, and training pipeline execution.
- [`docs/responsible_ai.md`](docs/responsible_ai.md): Privacy, explainability reason codes, fairness slicing, and human oversight.
- [`docs/report_draft.md`](docs/report_draft.md): 8-section submission report draft.
- [`docs/video_script.md`](docs/video_script.md): Demonstration video storyboard and narration script.
- [`docs/data_dictionary.md`](docs/data_dictionary.md): Synthetic data schema definitions and feature dictionary.
- [`docs/security_checklist.md`](docs/security_checklist.md): Secrets scan log and prompt injection hardening verification.
- [`docs/test_evidence.md`](docs/test_evidence.md): Automated test execution evidence across all suites.
- [`docs/demo_evidence.md`](docs/demo_evidence.md): End-to-end demo path execution log with verified API responses.
