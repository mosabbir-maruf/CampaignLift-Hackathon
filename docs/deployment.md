# Deployment Guide

This guide details the deployment procedures for CampaignLift using Docker Compose locally and on cloud VPS / AWS EC2 hosts.

---

## 1. Local Containerized Execution

CampaignLift runs as an isolated two-service composition defined in `docker-compose.yml`.

### Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- 4 GB RAM recommended

### Quickstart

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

2. **Launch Stack (Live Build)**:
   ```bash
   docker compose up --build -d
   ```
   Or pull pre-compiled multi-arch images from GitHub Container Registry (GHCR):
   ```bash
   docker compose pull
   docker compose up -d
   ```

3. **Verify Deployment Health**:
   ```bash
   # 1. Process Liveness Check (Nginx -> Backend)
   curl -i http://localhost/health
   # Expected: HTTP/1.1 200 OK {"status":"ok"}

   # 2. Dependency Readiness Check
   curl -i http://localhost/ready
   # Expected: HTTP/1.1 200 OK {"status":"ready","model_loaded":true,...}
   ```

4. **Access UI**:
   Open `http://localhost` in your browser.

---

## 2. Container Network Architecture

```
Host / External Network
       │
   [Port 80]
       ▼
┌───────────────────────────────────────────────┐
│ campaignlift-frontend (Nginx Alpine)          │
│ • Reverse proxy: /api/*  -> backend:8000      │
│ • Reverse proxy: /health -> backend:8000      │
│ • Reverse proxy: /ready  -> backend:8000      │
└───────────────────────┬───────────────────────┘
                        │ campaignlift-net (Docker Bridge)
                        ▼
┌───────────────────────────────────────────────┐
│ campaignlift-backend (FastAPI / Python 3.11)  │
│ • Internal Port 8000 (NOT published to host)  │
│ • Non-root execution (appuser, UID 1000)      │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
           campaignlift-db (Volume: /app/db)
```

---

## 3. Cloud Deployment (AWS EC2 / VPS)

### Infrastructure Specifications
- **Recommended Instance**: `t3.small` (2 vCPU, 2 GB RAM) or `t3.medium` (2 vCPU, 4 GB RAM).
- **OS**: Ubuntu 22.04 LTS or Amazon Linux 2023.
- **Security Group Ingress**:
  - `TCP 80` (HTTP) — Inbound from `0.0.0.0/0`
  - `TCP 443` (HTTPS) — Inbound from `0.0.0.0/0`
  - `TCP 22` (SSH) — Inbound from admin IP only
  - **Port 8000**: **BLOCKED** from public internet ingress.

### Deployment Workflow on EC2
1. Install Docker & Compose plugin:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
   sudo usermod -aG docker ubuntu
   ```
2. Clone repository or copy `docker-compose.yml` and `.env.example`:
   ```bash
   git clone https://github.com/mosabbir-maruf/CampaignLift-Hackathon.git
   cd CampaignLift-Hackathon
   cp .env.example .env
   ```
3. Set your production domain or IP and optional `GEMINI_API_KEY`:
   ```bash
   nano .env
   ```
4. Pull images and start daemon:
   ```bash
   docker compose pull
   docker compose up -d
   ```
5. Run the health verification script:
   ```bash
   curl -f http://localhost/ready || exit 1
   ```

### Live Production Status
The production environment is live at [https://devtree.online/](https://devtree.online/), running multi-architecture Docker containers on AWS EC2 with Cloudflare Origin Certificate TLS termination and automated health checks.
