# CampaignLift Production Infrastructure & Deployment Guide

This document specifies the production container deployment architecture, CI/CD pipeline, and operational procedures for CampaignLift on AWS EC2 or standard Linux VPS environments.

---

## 1. Architecture

CampaignLift uses a decoupled two-container architecture orchestrated by Docker Compose:

```
+-----------------------------------------------------------------------------------+
| Host VPS / AWS EC2 Instance                                                        |
|                                                                                   |
|  Public Ingress: Port 80 (or ${PORT})                                             |
|         │                                                                         |
|         ▼                                                                         |
|  +───────────────────────────────────────────────────+                            |
|  | campaignlift-frontend (Nginx Alpine)              |                            |
|  |  • Serves compiled React 19 SPA static assets     |                            |
|  |  • Client-side SPA routing fallback (index.html)  |                            |
|  |  • Static asset caching with immutable headers    |                            |
|  |  • Reverse proxy: /api/*  ───► http://api:8000/api|                            |
|  |  • Reverse proxy: /health ───► http://api:8000/hea|                            |
|  |  • Reverse proxy: /ready  ───► http://api:8000/rea|                            |
|  +─────────────────────────┬─────────────────────────+                            |
|                            │                                                      |
|       Isolated Docker      │ HTTP on internal port 8000                           |
|       Bridge Network       │ (Port 8000 NOT published to host)                    |
|       (campaignlift-net)   ▼                                                      |
|  +───────────────────────────────────────────────────+                            |
|  | campaignlift-backend (FastAPI / Python 3.11-slim) |                            |
|  |  • Uvicorn ASGI server with forwarded proxy hdrs  |                            |
|  |  • LightGBM inference & S-learner decision engine |                            |
|  |  • Non-root runtime user (appuser, UID 1000)      |                            |
|  |  • Pre-packaged model artifacts & feature tables  |                            |
|  |  • Optional server-side Gemini Copilot integration|                            |
|  +─────────────────────────┬─────────────────────────+                            |
|                            │                                                      |
|                            ▼                                                      |
|  +───────────────────────────────────────────────────+                            |
|  | Named Volume: campaignlift-db                      |                            |
|  |  • Persists SQLite database (/app/db) across       |                            |
|  |    container restarts, upgrades, and redeployments|                            |
|  +───────────────────────────────────────────────────+                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Local Production-Like Docker Compose Run

To test the exact production image deployment locally without building from source:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start the production stack in detached mode
docker compose up -d

# 3. Verify container status and healthchecks
docker compose ps

# 4. Test endpoints
curl -i http://localhost/health
curl -i http://localhost/ready
curl -i http://localhost/api/v1/campaigns

# 5. Stop the stack
docker compose down
```

---

## 3. GHCR Image Naming

Images are published to the GitHub Container Registry (GHCR) using lowercase-safe package names:

- **Frontend Image**: `ghcr.io/<owner>/campaignlift-frontend`
- **Backend Image**: `ghcr.io/<owner>/campaignlift-backend`

*Example:* `ghcr.io/mosabbir-maruf/campaignlift-frontend:latest`

---

## 4. CI Workflow

Automated testing and validation are executed by GitHub Actions (`.github/workflows/ci-cd.yml`):

### Pull Requests (`pull_request`)
- **Trigger**: Any pull request targeting the `main` branch.
- **Frontend Job**:
  - `actions/checkout@v7`
  - `actions/setup-node@v7` (Node 22)
  - `pnpm install --frozen-lockfile`
  - `pnpm run typecheck` (`tsc --noEmit`)
  - `pnpm run lint` (`oxfmt --check src`)
  - `pnpm run build` (`vite build`)
- **Backend Job**:
  - `actions/checkout@v7`
  - `actions/setup-python@v5` (Python 3.11)
  - Install dependencies (`libgomp1`, requirements, linters, pytest)
  - `ruff check --line-length=120 --select=E,F,W --ignore=E501 backend/app`
  - `mypy backend/app --ignore-missing-imports --explicit-package-bases`
  - `pytest backend/tests/ -v` (50 unit & integration tests)
- **Policy**: PRs execute validation ONLY. No Docker images are built or pushed on PRs.

### Push to `main` (`push`)
- Runs both Frontend and Backend quality gates.
- Upon successful validation, builds and publishes both Docker images to GHCR using Docker Buildx.
- Automatically triggers the GHCR retention cleanup script.

---

## 5. Image Tagging

Every image build pushed to `main` receives two tags:
1. `latest`: Mutable floating tag referencing the current tip of `main`.
2. `sha-<full-commit-sha>` (and `sha-<short-sha>`): Immutable Git commit SHA tag ensuring exact reproducibility and atomic rollback capability.

*Example:*
- `ghcr.io/mosabbir-maruf/campaignlift-backend:latest`
- `ghcr.io/mosabbir-maruf/campaignlift-backend:sha-614b08f883...`

---

## 6. GHCR Retention Policy

To manage registry storage efficiently and comply with retention standards:
- **Rule**: Retain only the newest **TWO (2)** published versions for each application image package (`campaignlift-frontend` and `campaignlift-backend`).
- **Implementation**: Handled by `scripts/cleanup-ghcr.py`.
- **Semantics**:
  - Fetches package versions from the GitHub API and sorts by `created_at` descending.
  - The two newest versions (by timestamp) are retained.
  - Any version bearing the `latest` tag is protected from deletion regardless of age.
  - Older versions are pruned.
  - Operates strictly on CampaignLift's packages; never touches third-party or unrelated packages.
  - Gracefully exits with a clear notice if running without package-deletion permissions.

---

## 7. VPS / AWS EC2 Deployment Procedure

A host machine requires only Docker Engine and Docker Compose. No host installation of Node.js, Python, npm, pip, or Nginx is needed.

### Step 1: Log in to GHCR on the Host
If images are private, authenticate using a GitHub Personal Access Token (PAT) with `read:packages` scope:
```bash
echo "$CR_PAT" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

### Step 2: Prepare Deployment Directory
```bash
mkdir -p /opt/campaignlift && cd /opt/campaignlift

# Download canonical docker-compose and environment template
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/.env.example -o .env
```

### Step 3: Configure Environment Variables
Edit `/opt/campaignlift/.env` with your deployment values:
```bash
nano .env
```
Ensure `FRONTEND_IMAGE` and `BACKEND_IMAGE` point to your GHCR repository.

### Step 4: Pull and Launch
```bash
# Pull latest images from GHCR
docker compose pull

# Start containers
docker compose up -d

# Verify containers are healthy
docker compose ps
```

---

## 8. Runtime Environment Variables

All secrets are runtime configuration only and must never be committed or baked into images:

| Variable | Scope | Default / Example | Purpose |
|---|---|---|---|
| `PORT` | Host / Compose | `80` | Host port mapped to Nginx reverse proxy |
| `FRONTEND_IMAGE` | Compose | `ghcr.io/<owner>/campaignlift-frontend:latest` | Frontend container image repository and tag |
| `BACKEND_IMAGE` | Compose | `ghcr.io/<owner>/campaignlift-backend:latest` | Backend container image repository and tag |
| `APP_ENV` | Backend | `production` | FastAPI execution environment |
| `LOG_LEVEL` | Backend | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | Backend | `sqlite:////app/db/campaignlift.db` | Persistent SQLite database connection URL |
| `MODEL_ARTIFACT_DIR` | Backend | `artifacts/models/...` | Path to ML model artifacts inside container |
| `FEATURE_TABLE_PATH` | Backend | `data/fixtures/fixture_v1/features.json` | Path to feature tables inside container |
| `DATASET_VERSION` | Backend | `cl-synth-ml_dev-20261006-8ad556a` | Active dataset version identifier |
| `GEMINI_API_KEY` | Backend | *(secret string)* | Optional Gemini API key for Copilot |
| `GEMINI_MODEL` | Backend | `gemini-2.5-flash` | Gemini model name for Copilot |

---

## 9. Health Checks & Verification

Both containers feature automated Docker `HEALTHCHECK` instructions:

- **Frontend Container**:
  - Probe: `wget -qO- http://127.0.0.1:80/ || exit 1`
  - Interval: `30s`, Timeout: `5s`, Retries: `3`
- **Backend Container**:
  - Probe: `curl -f http://localhost:8000/health || exit 1`
  - Interval: `10s`, Timeout: `5s`, Retries: `3`
- **Readiness Dependency**:
  - The `frontend` service waits for `backend` to achieve `condition: service_healthy` before routing incoming traffic.

---

## 10. Container Logs

View and follow container logs directly via Docker Compose:

```bash
# Combined output
docker compose logs -f

# Backend service logs
docker compose logs -f backend

# Frontend/Nginx access and error logs
docker compose logs -f frontend
```

---

## 11. Rollback Using Immutable SHA Tags

If a deployment must be rolled back to a previous known good version:

```bash
# Set specific immutable SHA tags in the environment or .env file
export FRONTEND_IMAGE=ghcr.io/<owner>/campaignlift-frontend:sha-<previous-commit-sha>
export BACKEND_IMAGE=ghcr.io/<owner>/campaignlift-backend:sha-<previous-commit-sha>

# Pull and redeploy
docker compose pull
docker compose up -d

# Verify running version
docker compose ps
```

---

## 12. Required AWS / VPS Manual Setup

The following steps are performed once on the host instance before first deployment:
1. **Provision Virtual Server**: Ubuntu 22.04/24.04 LTS or Amazon Linux 2023 on AWS EC2 (t3.small or t3.medium recommended) or VPS provider.
2. **Install Docker & Docker Compose**:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER
   ```
3. **Configure Firewall / Security Groups**:
   - Inbound TCP `80` (HTTP) from `0.0.0.0/0`
   - Inbound TCP `443` (HTTPS) from `0.0.0.0/0` (if terminating SSL with Certbot or ALB)
   - Inbound TCP `22` (SSH) from trusted administrator IP only
   - Internal port `8000` must **NOT** be open in the firewall or AWS Security Group.
4. **Configure DNS**: Point your domain name (A Record) to the VPS/EC2 public elastic IP.
5. **(Optional) HTTPS Termination**: Use Let's Encrypt / Certbot on the host or place an AWS Application Load Balancer (ALB) in front of Port 80.

---

## 13. What Is Automated by GitHub Actions

- Automated lint checks on every PR and push (oxfmt for frontend, ruff for backend).
- Automated type checks on every PR and push (TypeScript `tsc` for frontend, `mypy` for backend).
- Automated execution of all 50 unit and integration tests on backend.
- Automated production bundle compilation of frontend SPA.
- Automated multi-stage Docker build of `campaignlift-frontend`.
- Automated Docker build of `campaignlift-backend`.
- Automated publication of images to GitHub Container Registry (`ghcr.io`).
- Automated generation of `latest` and immutable `sha-<commit-sha>` tags.
- Automated cleanup of old GHCR image versions, enforcing retention of the 2 newest versions.

---

## 14. What Requires Manual Infrastructure Setup

The following aspects remain intentionally under manual or external operator control to keep infrastructure simple, transparent, and portable:
- Initial VPS / AWS EC2 server creation and base OS installation.
- Security group and firewall configuration (ports 80, 443, 22).
- Domain DNS record management.
- Initial creation of `/opt/campaignlift/.env` with production secrets (`GEMINI_API_KEY`).
- Docker login authentication on the server for private GHCR access.
- Invocation of `docker compose pull && docker compose up -d` on the server during scheduled releases (or through an optional lightweight webhook listener).
