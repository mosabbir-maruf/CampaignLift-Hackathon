# Reproducibility Guide

This guide provides the seeds, configurations, dataset versions, and execution commands required to reproduce the synthetic data generation and uplift model training pipelines.

---

## 1. Deterministic Seeds & Configuration

To ensure end-to-end reproducibility across synthetic data generation, sampling, model training, and evaluation, the pipeline uses fixed global and stage seeds.

- **Global Seed**: `20261006`
- **Config File**: `data/config/world.yaml`
- **Deterministic Stage Seeds**:
  - Customer Generation: `20261006 + 101`
  - Transaction History: `20261006 + 202`
  - Campaign Scenarios: `20261006 + 303`
  - Treatment Assignment: `20261006 + 404`
  - Outcome Simulation: `20261006 + 505`
  - Train/Val/Test Split: `20261006 + 606`

---

## 2. Dataset Versions & Manifests

All datasets include cryptographic SHA-256 manifests (`data/manifests/`):

1. **`fixture_v1`** (`data/fixtures/fixture_v1/`):
   - 103 customers, 3,964 transactions.
   - Purpose: Deterministic unit tests, CI test runs, and smoke testing.
2. **`dev`** (`cl-synth-dev-20261006-8ad556a`):
   - 5,000 customers, 101,842 transactions.
   - Purpose: Integration testing and local development.
3. **`ml_dev`** (`cl-synth-ml_dev-20261006-8ad556a`):
   - 25,000 customers, 509,244 transactions.
   - Purpose: ML candidate training, cross-validation, and final model selection.
4. **`benchmark` (100k customers)**:
   - Status: Deferred from local repository per Decision D-024 to avoid unneeded workstation disk saturation.

---

## 3. Training the Uplift Models

### Local Training & Verification
To execute the uplift training script locally against the development dataset:

```bash
# Run model training and validation pipeline
python -m ml.src.campaignlift_ml.uplift

# Run strategy comparison evaluator
python -m ml.src.campaignlift_ml.compare

# Run demographic slice fairness and oracle report
python -m ml.src.campaignlift_ml.report
```

### Kaggle Training Workflow (`ml/notebooks/kaggle_train.ipynb`)
- **Environment**: Python 3.11, standard Kaggle CPU or GPU environment.
- **Dependencies**: LightGBM 4.7+, scikit-learn 1.9+, pandas 3.0+, numpy 2.4+.
- **Protocol**:
  1. Load `ml_dev` dataset release partitions.
  2. Fit candidate architectures (Response baseline, Logistic T-Learner, LightGBM T-Learner, LightGBM S-Learner).
  3. Evaluate candidate models on validation split using normalized Qini (AUUC).
  4. Freeze winning model: `LightGBM S-Learner` (`candidate_id: U2`).
  5. Touch test split once to record unbiased evaluation metrics.
  6. Package model artifact directory with `model.joblib`, `metadata.json`, and `feature_list.json`.

---

## 4. Serving the Trained Artifact

The winning artifact is placed under:
`artifacts/models/cl-model-ml_dev_20261006-lgbm_s_learner-r01/`

The FastAPI backend loads this packaged artifact directly at startup. Kaggle is used exclusively as a training workbench, never as a live runtime API dependency.
