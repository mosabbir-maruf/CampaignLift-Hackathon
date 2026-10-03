# CampaignLift Backend API Service
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, libgomp1 for LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application modules, model artifacts, and data fixtures
COPY backend/ /app/backend/
COPY artifacts/ /app/artifacts/
COPY data/ /app/data/

# Runtime environment configuration
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    APP_ENV=local \
    LOG_LEVEL=INFO

# Internal port only — NOT published to host
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
