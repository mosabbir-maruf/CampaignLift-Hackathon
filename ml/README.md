# CampaignLift Machine Learning & Kaggle Training Architecture

This directory contains the machine learning modeling pipelines, uplift candidate learners, model selection logic, training notebooks, and artifact packaging specifications for CampaignLift.

---

## 1. Cloud Training vs. Serving Architecture

To maintain reproducibility, compute efficiency, and clear separation of concerns:
* **Training Platform (Kaggle)**: All model training, hyperparameter fitting, cross-validation, and candidate selection are executed on Kaggle (or local compute via identical entry points).
* **Serving Platform (FastAPI)**: Trained model artifacts (`artifacts/models/<model_version>/`) are downloaded from Kaggle outputs and served by the FastAPI application for real-time inference and budget optimization.
* **Non-Goals for Kaggle**:
  * Kaggle is **never** a live API dependency or runtime service.
  * Kaggle does **not** host customer-facing endpoints.
  * Kaggle is **never** used to edit data generators without committing code back to the internal repository.

---

## 2. Kaggle Upload Protocol: Allowlist vs. Denylist

> **Validation Criterion**: A reader must be able to unambiguously distinguish which files are uploaded to Kaggle and which are strictly forbidden from upload.

### A. Upload Allowlist (What Goes to Kaggle)

| Target Kaggle Resource | Local Source Files | Description |
| :--- | :--- | :--- |
| **Training Dataset** (`campaignlift-dataset`) | `features.json` | Pre-assignment feature store (RFM, demographic features). |
| | `splits.json` | Deterministic 60/20/20 train/val/test cohort split mappings. |
| | `manifest.json` | Release checksums, row counts, and seed audit metadata. |
| | `campaign.json` | Target campaign parameters (incentives, costs, offer types). |
| **Evaluation Oracle** (`campaignlift-oracle`) *(Optional)* | `hidden_uplift.json` | **STRICTLY SEPARATED**: Uploaded *only* as a distinct dataset with `-oracle` suffix for post-selection ground-truth benchmark comparison. |
| **Code Bundle** (`/kaggle/working/`) | `ml/src/campaignlift_ml/**` | Python packages containing data loader, baseline models, T-learners, S-learner, and metrics. |
| | `ml/requirements.txt` | Pinned dependency specifications. |
| | `ml/notebooks/kaggle_train.ipynb` | Execution wrapper setting path contracts. |

### B. Upload Denylist (Strictly FORBIDDEN from Kaggle)

| Forbidden Category | Files / Directories | Rationale |
| :--- | :--- | :--- |
| **Internal Planning & Decisions** | `planning/**`, `tasks/**`, `decisions/**` | Internal contest strategies and scratch records must remain private. |
| **Credentials & Secrets** | `.env`, API keys (`GEMINI_API_KEY`), AWS tokens | Security violation; credentials must never leave local environments. |
| **Raw Transaction Data** | `data/generated/**/transactions.json` | Unaggregated 2M+ raw transaction tables are unnecessary for feature-trained models. |
| **Oracle in Training Inputs** | `hidden_uplift.json` inside `campaignlift-dataset` | **Absolute Causal Breach**: Unobservable potential outcomes ($p_0, p_1, \tau$) must never be accessible during model fitting. |
| **Agent History** | Agent logs, scratch scripts, IDE metadata | Development session artifacts not relevant to clean reproducible training. |

---

## 3. Strict Oracle Dataset Isolation

To protect causal validity:
1. `hidden_uplift.json` contains ground-truth counterfactuals ($p_{\text{control}}$, $p_{\text{treat}}$, $\tau = p_{\text{treat}} - p_{\text{control}}$).
2. The training notebook and training script **never list the oracle dataset as an input**.
3. The dataset loader (`campaignlift_ml.loader`) cryptographically enforces that no forbidden column from `data/schemas/FORBIDDEN_TRAINING_COLUMNS.txt` enters training matrices.
4. If attached, `campaignlift-oracle` is accessed *only* during Stage 9 (post-selection evaluation) to record `outputs/oracle_metrics.json` labeled explicitly as `synthetic_oracle`.

---

## 4. Path Contracts & Notebook Execution

The notebook [`ml/notebooks/kaggle_train.ipynb`](file:///c:/Users/Assaduzzaman/Coding/CampaignLift-Internal/ml/notebooks/kaggle_train.ipynb) adheres to the following path contracts:

* **Kaggle Environment**:
  * Input features: `/kaggle/input/campaignlift-dataset/`
  * Optional oracle: `/kaggle/input/campaignlift-oracle/`
  * Output artifacts: `/kaggle/working/outputs/`
  * Execution command:
    ```bash
    python -m campaignlift_ml.train \
      --dataset-dir /kaggle/input/campaignlift-dataset \
      --output-dir /kaggle/working/outputs \
      [--oracle-dir /kaggle/input/campaignlift-oracle]
    ```
* **Local Workstation Fallback** (for CI and smoke tests):
  * Input features: `data/fixtures/fixture_v1` or `data/generated/ml_dev`
  * Output artifacts: `ml/outputs`

---

## 5. Execution Pipeline Stages

The training pipeline executes 10 sequential stages:
1. **Manifest Audit**: Print dataset version, global seed, and SHA-256 file checksums.
2. **Anti-Leakage Check**: Verify feature columns against `FORBIDDEN_TRAINING_COLUMNS.txt`.
3. **Partition Isolation**: Load `train` and `val` splits only; test split remains untouched.
4. **Candidate Fitting**: Fit response baseline (B0), logistic S-learner (B1), logistic T-learner (U0), LightGBM T-learner (U1), and LightGBM S-learner (U2).
5. **Validation Metrics**: Evaluate validation Qini, AUUC, and cumulative incremental gains; write `outputs/validation_metrics.json`.
6. **Model Selection**: Apply pre-committed selection rules; write `outputs/selection.json` with winner and rejected candidates.
7. **Refit Winner**: Refit the winning model on `train + val`.
8. **Test Scoring**: Score the held-out `test` split once; write `outputs/test_metrics.json`.
9. **Oracle Evaluation** *(Optional)*: If `-oracle` dataset is attached, compute synthetic alignment metrics and write `outputs/oracle_metrics.json`.
10. **Artifact Packaging**: Save model binary and `metadata.json` to output directory for deployment.

---

## 6. Artifact Export Specification

The output package produced for FastAPI serving (`artifacts/models/<model_version>/`) consists of:

| Artifact File | Committed to Git? | Description |
| :--- | :---: | :--- |
| `metadata.json` | **Yes** | Model architecture, features list, dataset SHA, seed, and metrics. |
| `feature_list.json` | **Yes** | Ordered feature schema expected by inference routes. |
| `validation_metrics.json` | **Yes** | Qini curve and evaluation numbers across all candidates. |
| `test_metrics.json` | **Yes** | Single-evaluation test set metrics for the selected model. |
| `oracle_metrics.json` | **Yes** *(if created)* | Ground-truth alignment metrics labeled `synthetic_oracle`. |
| `<model_binary>.joblib` | **No** *(if > 10MB)* | Serialized scikit-learn / LightGBM estimators. Stored in S3 or release bundle. |

---

## 7. Model Versioning Scheme

Model versions follow the canonical format:
```text
cl-model-<dataset_version>-<family>-<run_number>
```
* Example: `cl-model-ml_dev_20261006-lgbm_t_learner-r01`
