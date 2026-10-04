# CampaignLift Production Infrastructure & Deployment Guide

Production container topology, Cloudflare TLS ingress, CI/CD automation, and AWS EC2 operational runbook.

<p align="left">
  <a href="https://devtree.online/">
    <img src="https://img.shields.io/badge/Live_Demo-devtree.online-2ea44f.svg?logo=cloudflare&logoColor=white" alt="Live Demo" />
  </a>
  <a href="https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-backend">
    <img src="https://img.shields.io/badge/Docker-backend--image-2496ed.svg?logo=docker&logoColor=white" alt="Docker Backend Image" />
  </a>
  <a href="https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-frontend">
    <img src="https://img.shields.io/badge/Docker-frontend--image-2496ed.svg?logo=docker&logoColor=white" alt="Docker Frontend Image" />
  </a>
  <a href="../docker-compose.yml">
    <img src="https://img.shields.io/badge/Docker_Compose-v2.20+-2496ed.svg?logo=docker&logoColor=white" alt="Docker Compose" />
  </a>
  <a href="https://docs.aws.amazon.com/ec2/">
    <img src="https://img.shields.io/badge/AWS-EC2-FF9900.svg?logo=amazonec2&logoColor=white" alt="AWS EC2" />
  </a>
  <a href="https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/">
    <img src="https://img.shields.io/badge/Cloudflare-SSL%20Origin-F38020.svg?logo=cloudflare&logoColor=white" alt="Cloudflare SSL" />
  </a>
  <a href="../LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
  </a>
</p>

---

## 1. Production Architecture

CampaignLift operates as a decoupled two-container micro-stack orchestrated by Docker Compose behind a hardened Nginx reverse proxy with TLS termination:

```text
+-----------------------------------------------------------------------------------------+
| Host: AWS EC2 Ubuntu 24.04 LTS (devtree.online)                                         |
|                                                                                         |
|  Public Ingress: Port 80 (HTTP) -> 301 Redirect to HTTPS                                |
|  Public Ingress: Port 443 (HTTPS) with Cloudflare Origin Certificate TLS                |
|         │                                                                               |
|         ▼                                                                               |
|  +─────────────────────────────────────────────────────────+                            |
|  | campaignlift-frontend (Nginx 1.27 Alpine)               |                            |
|  |  • Port 80: HTTP-to-HTTPS permanent redirect (301)       |                            |
|  |  • Port 443: TLS termination (/etc/nginx/certs/ro)      |                            |
|  |  • Serves compiled React 19 SPA static assets           |                            |
|  |  • Client-side SPA routing fallback (index.html)        |                            |
|  |  • Static asset caching with immutable Cache-Control    |                            |
|  |  • Reverse proxy: /api/*  ───► http://api:8000/api/*    |                            |
|  |  • Health proxy:  /health ───► http://api:8000/health    |                            |
|  |  • Health proxy:  /ready  ───► http://api:8000/ready     |                            |
|  +────────────────────────────┬────────────────────────────+                            |
|                               │                                                         |
|       Isolated Docker         │ HTTP on internal port 8000                              |
|       Bridge Network          │ (Port 8000 NOT published to host)                       |
|       (campaignlift-net)      ▼                                                         |
|  +─────────────────────────────────────────────────────────+                            |
|  | campaignlift-backend (FastAPI / Python 3.11-slim)       |                            |
|  |  • Uvicorn ASGI server with forwarded proxy headers     |                            |
|  |  • Causal uplift inference (LightGBM S-Learner)         |                            |
|  |  • Greedy knapsack budget optimizer                     |                            |
|  |  • Pre-packaged model artifacts & feature tables        |                            |
|  |  • Grounded Google Gemini 2.5 Flash decision copilot    |                            |
|  |  • Non-root runtime user (appuser, UID 1000)            |                            |
|  +────────────────────────────┬────────────────────────────+                            |
|                               │                                                         |
|                               ▼                                                         |
|  +─────────────────────────────────────────────────────────+                            |
|  | Named Volume: campaignlift-db                           |                            |
|  |  • Persists SQLite database (/app/db/campaignlift.db)   |                            |
|  |    across container restarts, upgrades, and redeploys   |                            |
|  +─────────────────────────────────────────────────────────+                            |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Live Production Deployment

The production application is live and publicly verified:

- **Primary Application URL**: [https://devtree.online/](https://devtree.online/)
- **Alternative Ingress**: [https://www.devtree.online/](https://www.devtree.online/)
- **Liveness Probe**: `https://devtree.online/health` (HTTP 200 `{"status":"ok"}`)
- **Readiness Probe**: `https://devtree.online/ready` (HTTP 200 `{"status":"ready", ...}`)
- **Hosting Platform**: AWS EC2 VPS running Ubuntu Linux
- **SSL/TLS Mode**: Cloudflare Full (strict Origin Certificate validation)
- **Container Registry**: GitHub Container Registry (`ghcr.io`)

---

## 3. GHCR Image Registry & Multi-Arch Distribution

Pre-built multi-architecture images (`linux/amd64`, `linux/arm64`) are published to the GitHub Container Registry:

| Service | Container Image | Target Architecture |
| :--- | :--- | :--- |
| **Frontend Workstation** | `ghcr.io/mosabbir-maruf/campaignlift-frontend:latest` | `linux/amd64`, `linux/arm64` |
| **Backend API Engine** | `ghcr.io/mosabbir-maruf/campaignlift-backend:latest` | `linux/amd64`, `linux/arm64` |

*Package registries:*
- Frontend: [`ghcr.io/mosabbir-maruf/campaignlift-frontend`](https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-frontend)
- Backend: [`ghcr.io/mosabbir-maruf/campaignlift-backend`](https://github.com/mosabbir-maruf/CampaignLift-Hackathon/pkgs/container/campaignlift-backend)

---

## 4. Local Production-Like Run

To test the exact production multi-container stack locally without compiling from source:

```bash
# 1. Clone repository
git clone https://github.com/mosabbir-maruf/CampaignLift-Hackathon.git
cd CampaignLift-Hackathon

# 2. Copy canonical environment configuration
cp .env.example .env

# 3. Pull latest pre-built container images
docker compose pull

# 4. Start the stack in detached mode
docker compose up -d

# 5. Verify service health
docker compose ps

# 6. Test health endpoints
curl -f http://localhost/health
curl -f http://localhost/ready

# 7. Stop the stack
docker compose down
```

---

## 5. Automated CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci-cd.yml`) automates verification, multi-arch packaging, and registry retention:

### Quality Gates (Pull Requests & Pushes)
1. **Frontend Gate**:
   - Node 22 setup with pnpm.
   - TypeScript compile-time verification: `pnpm run typecheck` (`tsc --noEmit`).
   - Linter and style checks: `pnpm run lint` (`oxfmt --check src`).
   - Production bundle compilation: `pnpm run build` (`vite build`).
2. **Backend Gate**:
   - Python 3.11 setup with dependency caching.
   - Code formatting & linting: `ruff check backend/app`.
   - Static type checking: `mypy backend/app`.
   - Automated unit & integration tests: `pytest backend/tests/ -v` (50 passing tests).

### Automated Build & Publish (`main` Branch Push Only)
- Sets up QEMU and Docker Buildx.
- Authenticates to GitHub Container Registry (`ghcr.io`).
- Builds dual-architecture images (`linux/amd64`, `linux/arm64`) with `provenance: false` to ensure multi-arch manifest compatibility.
- Tags images with `latest`, `sha-<short-sha>`, and `sha-<full-sha>`.
- Executes automated package retention cleanup via `scripts/cleanup-ghcr.py`.

---

## 6. Image Tagging & Rollback Strategy

Every build published to `ghcr.io` receives both mutable and immutable tags:
- `latest`: Floating tag pointing to the latest successful build on `main`.
- `sha-<commit-sha>`: Immutable tag linking directly to the Git commit SHA.

### Atomic Rollback Procedure
If a regression occurs, revert immediately to an immutable SHA image without rebuilding:

```bash
# Set target commit tags in .env
export FRONTEND_IMAGE=ghcr.io/mosabbir-maruf/campaignlift-frontend:sha-<known-good-sha>
export BACKEND_IMAGE=ghcr.io/mosabbir-maruf/campaignlift-backend:sha-<known-good-sha>

# Pull and redeploy
docker compose pull
docker compose up -d

# Verify rollback
docker compose ps
```

---

## 7. Registry Retention Policy

To manage registry disk footprint cleanly:
- **Policy**: Retains only the newest **2 versions** for both `campaignlift-frontend` and `campaignlift-backend`.
- **Implementation**: Handled automatically in CI by `scripts/cleanup-ghcr.py`.
- **Protection**: Tags containing `latest` are protected from deletion.
- **Safety**: Multi-arch parent manifest lists and child platform layers are preserved without breaking manifest trees.

---

## 8. AWS EC2 Production Deployment Runbook

### Host Requirements
- **OS**: Ubuntu 22.04 LTS or 24.04 LTS
- **Instance Sizing**: `t3.small` (2 vCPU, 2 GB RAM) or `t3.medium`
- **Installed Software**: Docker Engine 24.0+ and Docker Compose v2.20+

### Step-by-Step Production Setup

1. **Install Docker Engine**:
   ```bash
   sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
   sudo usermod -aG docker $USER
   ```

2. **Configure Host Security Group / Firewall**:
   - `TCP 80` (HTTP) from `0.0.0.0/0` (Nginx permanent redirect to HTTPS)
   - `TCP 443` (HTTPS) from `0.0.0.0/0` (Nginx TLS termination)
   - `TCP 22` (SSH) restricted to authorized management IPs
   - `TCP 8000` **NOT published** to the host or internet (strictly internal to Docker bridge)

3. **Install Cloudflare Origin Certificates**:
   ```bash
   mkdir -p /home/ubuntu/campaignlift/certs
   chmod 700 /home/ubuntu/campaignlift/certs

   # Place Origin Certificate and Key
   nano /home/ubuntu/campaignlift/certs/origin.pem
   nano /home/ubuntu/campaignlift/certs/origin.key
   chmod 600 /home/ubuntu/campaignlift/certs/origin.key
   ```

4. **Deploy Application Stack**:
   ```bash
   mkdir -p /home/ubuntu/campaignlift && cd /home/ubuntu/campaignlift

   # Clone or pull configuration
   git clone https://github.com/mosabbir-maruf/CampaignLift-Hackathon.git .
   cp .env.example .env

   # Pull pre-built images and start daemon
   docker compose pull
   docker compose up -d
   ```

5. **Verify Running Services**:
   ```bash
   docker compose ps
   curl -k https://localhost/health
   curl -k https://localhost/ready
   ```

---

## 9. HTTPS Termination & Cloudflare Configuration

CampaignLift implements end-to-end TLS encryption:

1. **DNS**:
   - `devtree.online` -> A Record pointing to EC2 Public Elastic IP (Proxied through Cloudflare).
   - `www.devtree.online` -> CNAME pointing to `devtree.online` (Proxied).
2. **Cloudflare SSL/TLS Encryption Mode**:
   - Set to **Full** (strict encryption between Cloudflare edge and EC2 origin).
3. **Nginx Container Ingress (`frontend/nginx.conf`)**:
   - Port 80 server block receives plain HTTP and responds with `301 Moved Permanently` to `https://$host$request_uri`.
   - Port 443 server block terminates TLS using `/etc/nginx/certs/origin.pem` and `/etc/nginx/certs/origin.key`.
   - All certificates are mounted **read-only** (`:ro`) and are never committed to version control.

---

## 10. Runtime Environment Variables Matrix

All configuration is supplied at runtime via `.env`:

| Variable | Scope | Default / Value | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Host / Ingress | `80` | Host HTTP ingress port |
| `CERTS_DIR` | Host / Ingress | `/home/ubuntu/campaignlift/certs` | Host directory containing SSL certificates |
| `FRONTEND_IMAGE` | Docker Compose | `ghcr.io/mosabbir-maruf/campaignlift-frontend:latest` | Frontend container image repository |
| `BACKEND_IMAGE` | Docker Compose | `ghcr.io/mosabbir-maruf/campaignlift-backend:latest` | Backend container image repository |
| `APP_ENV` | Backend | `production` | Execution environment (`local`, `production`) |
| `LOG_LEVEL` | Backend | `INFO` | Application log verbosity |
| `DATABASE_URL` | Backend | `sqlite:////app/db/campaignlift.db` | Persistent SQLite database file URI |
| `MODEL_ARTIFACT_DIR` | Backend | `artifacts/models/...` | Path to trained LightGBM model artifact directory |
| `FEATURE_TABLE_PATH` | Backend | `data/fixtures/fixture_v1/features.json` | Path to customer cohort feature fixture |
| `DATASET_VERSION` | Backend | `cl-synth-ml_dev-20261006-8ad556a` | Version identifier for synthetic MFS dataset |
| `GEMINI_API_KEY` | Backend | `""` | Google Gemini API key for decision copilot |
| `GEMINI_MODEL` | Backend | `gemini-2.5-flash` | Gemini model name |

---

## 11. Health Checks & Verification

Docker Compose monitors service health automatically:

```bash
# Check service health status
docker compose ps

# Inspect live container logs
docker compose logs -f

# Backend service logs
docker compose logs -f backend

# Frontend Nginx proxy logs
docker compose logs -f frontend
```

- **Frontend Health**: Probes Nginx local web server every 30s.
- **Backend Health**: Probes `/health` every 10s.
- **Service Dependency**: The frontend depends on backend achieving `service_healthy` before routing incoming requests.
