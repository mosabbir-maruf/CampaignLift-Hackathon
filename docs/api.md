# CampaignLift API Documentation

The CampaignLift Decision Engine exposes a RESTful API implemented with FastAPI and Pydantic v2. Interactive OpenAPI documentation is available locally at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## 1. System & Lifecycle Endpoints

### `GET /health`
- **Summary**: Liveness probe.
- **Description**: Returns process health without invoking external dependencies or disk I/O.
- **Responses**:
  - `200 OK`: `{"status": "ok"}`

### `GET /ready`
- **Summary**: Readiness probe.
- **Description**: Confirms that the machine learning model is loaded in memory, the customer feature table is readable, and the SQLite database is writable.
- **Responses**:
  - `200 OK`:
    ```json
    {
      "status": "ready",
      "model_loaded": true,
      "model_version": "cl-model-ml_dev_20261006-lgbm_s_learner-r01",
      "dataset_version": "cl-synth-ml_dev-20261006-8ad556a",
      "feature_file_readable": true,
      "database_writable": true
    }
    ```
  - `503 Service Unavailable`: If model artifacts or dependencies fail verification.

---

## 2. Campaign Management & Scoring Endpoints

### `POST /api/v1/campaigns`
- **Summary**: Create campaign definition.
- **Description**: Creates and persists a marketing campaign scenario. Rejects uploaded customer lists to enforce pre-generated, validated cohort isolation.
- **Request Body**:
  ```json
  {
    "name": "Q4 Persuadables Growth Drive",
    "objective": "activation",
    "offer_type": "flat_cashback",
    "incentive_value": 50.0,
    "incentive_cost_bdt": 50.0,
    "budget_bdt": 2500.0,
    "channel": "in_app"
  }
  ```
- **Responses**:
  - `201 Created`: Returns created campaign object with generated `id` and timestamps.
  - `400 Bad Request`: If invalid parameters or forbidden customer list keys are provided.

### `GET /api/v1/campaigns/{id}`
- **Summary**: Retrieve campaign scenario.
- **Responses**:
  - `200 OK`: Campaign metadata.
  - `404 Not Found`: Campaign does not exist.

### `POST /api/v1/campaigns/{id}/score`
- **Summary**: Population uplift scoring.
- **Description**: Scores all eligible customers for the campaign using the active model artifact.
- **Query Parameters**:
  - `limit` (int, default 50, max 500)
  - `offset` (int, default 0)
- **Responses**:
  - `200 OK`:
    ```json
    {
      "run_id": "run_20261004_041453_eb3b70",
      "campaign_id": "camp_20261004_207362",
      "model_version": "cl-model-ml_dev_20261006-lgbm_s_learner-r01",
      "dataset_version": "cl-synth-ml_dev-20261006-8ad556a",
      "total_eligible": 103,
      "total_scored": 103,
      "uplift_deciles": [...],
      "items": [
        {
          "customer_id": "C00000170",
          "eligible": true,
          "p_treat": 0.753196,
          "p_control": 0.650884,
          "uplift": 0.102312,
          "response_rank": 19,
          "uplift_rank": 1
        }
      ]
    }
    ```

---

## 3. Decision Optimization & Strategy Comparison

### `POST /api/v1/campaigns/{id}/optimize`
- **Summary**: Budget optimization.
- **Description**: Runs greedy knapsack ranking by expected incremental transaction value. Filters out negative-uplift customers when configured.
- **Request Body**:
  ```json
  {
    "budget_bdt": 2500.0,
    "exclude_negative_uplift": true,
    "value_per_incremental_transaction_bdt": 200.0
  }
  ```
- **Responses**:
  - `200 OK`: Returns audience allocation, spend, expected value, and comparison breakdown.

### `GET /api/v1/campaigns/{id}/comparison`
- **Summary**: Strategy comparison matrix.
- **Description**: Compares Random, Response Model, and Uplift Model allocations under identical budget constraints.
- **Responses**:
  - `200 OK`: Returns side-by-side metrics including customer counts, expected incremental value, and negative uplift share.

---

## 4. Explanations & LLM Copilot

### `GET /api/v1/campaigns/{id}/customers/{customer_id}/explanation`
- **Summary**: Customer feature attribution.
- **Description**: Computes linear feature contributions and maps them to deterministic reason codes (`incremental_candidate`, `likely_without_offer`, `weak_response`, `negative_uplift`).
- **Responses**:
  - `200 OK`:
    ```json
    {
      "customer_id": "C00000170",
      "p_treat": 0.7532,
      "p_control": 0.6509,
      "uplift": 0.1023,
      "reason_code": "incremental_candidate",
      "template_text": "...",
      "feature_contributions": [...]
    }
    ```

### `POST /api/v1/campaigns/{id}/copilot`
- **Summary**: Grounded LLM Copilot assistant.
- **Description**: Answers managerial questions strictly from the verified run JSON context. Rejects prompt injection and ignores instructions to override safety guardrails.
- **Request Body**:
  ```json
  {
    "run_id": "run_20261004_041453_eb3b70",
    "question": "Why was customer C00000170 prioritized?"
  }
  ```
- **Responses**:
  - `200 OK`: Grounded natural language response with `context_fields_used`.
  - `503 Service Unavailable`: If `GEMINI_API_KEY` is not configured or the service is temporarily unreachable.

---

## 5. Experiment Intelligence

### `GET /api/v1/campaigns/{id}/experiment`
- **Summary**: Simulated trial evaluation.
- **Description**: Computes factual conversion rates across treatment and control arms for simulated trials. Evaluates 23 demographic and behavioral slices and enforces the 30/30 minimum randomized support rule.
- **Responses**:
  - `200 OK`: Trial conversion rates, incremental lift, and slice breakdowns.
