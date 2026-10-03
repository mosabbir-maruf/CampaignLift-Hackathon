# CampaignLift Local Infrastructure & Docker Compose

This directory documents the local containerized environment for CampaignLift frontend and FastAPI decision support services.

## Prerequisites
- Docker Engine >= 24.0 or Docker Desktop
- Docker Compose v2 (e.g. `docker compose`)
- Ports available: Port 80 (configurable via `PORT` variable)

## Service Architecture
- **`web`**: Production Nginx container serving the compiled React SPA. Publishes port 80 to the host and reverse-proxies `/api/` calls to the `api` service.
- **`api`**: Python 3.11 container running the FastAPI decision support service with Uvicorn. Exposes internal port 8000 only within the Docker network. The host cannot access port 8000 directly.
- **`campaignlift-net`**: Isolated bridge network enabling service name resolution (`http://api:8000`).

## Quick Start

### 1. Build and Start the Stack
From the repository root:
```bash
# Build and run containers in detached mode
docker compose up --build -d
```

To run on a different host port (e.g. 8080):
```bash
PORT=8080 docker compose up --build -d
```

### 2. Verify Services and Health Checks
- **Frontend Workstation**: Open [http://localhost](http://localhost) (or `http://localhost:8080`)
- **API Liveness Probe**:
  ```bash
  curl -i http://localhost/health
  # HTTP/1.1 200 OK -> {"status":"ok"}
  ```
- **API Readiness Probe**:
  ```bash
  curl -i http://localhost/ready
  ```
- **API Reverse Proxy Route**:
  ```bash
  curl -i http://localhost/api/v1/campaigns
  ```

### 3. Inspect Container Logs
```bash
# View combined logs
docker compose logs -f

# View backend API logs only
docker compose logs -f api

# View web access logs only
docker compose logs -f web
```

### 4. Stop the Environment
```bash
# Stop containers
docker compose stop

# Stop and remove containers and networks
docker compose down
```

## Security & Environment Rules
- **No Hardcoded Secrets**: Never commit `.env` files, API keys (including `GEMINI_API_KEY`), or cloud credentials to Git or bake them into Docker images.
- **Internal API Isolation**: The API port 8000 is intentionally kept internal to the Docker network. All ingress traffic flows through the reverse proxy.
- **Session State**: SQLite databases and logs generated inside containers stay isolated.
