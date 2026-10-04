# CampaignLift Machine Learning & Causal Inference Engine

Causal uplift modeling, counterfactual inference pipelines, Qini evaluation, and model artifact packaging.

<p align="left">
  <a href="https://github.com/mosabbir-maruf/CampaignLift-Hackathon/blob/main/ml/notebooks/kaggle_train.ipynb">
    <img src="https://img.shields.io/badge/Kaggle-Notebook-20BEFF.svg?logo=kaggle&logoColor=white" alt="Kaggle Notebook" />
  </a>
  <a href="https://www.python.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white" alt="Python 3.11" />
  </a>
  <a href="https://lightgbm.readthedocs.io/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/ML-LightGBM-brightgreen.svg" alt="LightGBM" />
  </a>
  <a href="https://scikit-learn.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/scikit--learn-1.3+-F7931E.svg?logo=scikitlearn&logoColor=white" alt="scikit-learn" />
  </a>
  <a href="https://pandas.pydata.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/pandas-2.1+-150458.svg?logo=pandas&logoColor=white" alt="pandas" />
  </a>
  <a href="https://docs.pytest.org/" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/badge/Tests-pytest-0a9edc.svg?logo=pytest&logoColor=white" alt="pytest" />
  </a>
  <a href="../LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
  </a>
</p>

---

## 1. Overview & Causal Formulation

Traditional marketing campaigns optimize for **Response Propensity**—the probability that a customer transacts when offered an incentive:
$$P(\text{transact} \mid X, \text{offer}=1)$$

This strategy leads to substantial deadweight loss:
- **Incentive Cannibalization**: Marketing budget is squandered on **"Sure Things"**—customers who would have completed transactions organically without incentives.
- **Customer Fatigue**: Badgering sensitive customers triggers negative reactions (**"Sleeping Dogs"**), accelerating unprompted churn.

**CampaignLift** formulates campaign targeting as an **Incremental Causal Uplift** problem:
$$\tau(X) = P(\text{transact} \mid X, \text{offer}=1) - P(\text{transact} \mid X, \text{offer}=0)$$

By directly estimating $\tau(X)$, CampaignLift isolates true **"Persuadables"** from "Sure Things" and "Sleeping Dogs", maximizing net incremental transaction volume under fixed marketing budgets.

---

## 2. Directory Structure

```text
ml/
├── config/
│   └── train.yaml                   # Training hyperparameters, feature sets & split paths
├── experiments/
│   ├── selection.json               # Model selection tournament outcome and candidate metrics
│   └── metadata_draft.json          # Pre-deployment artifact schema definition
├── notebooks/
│   └── kaggle_train.ipynb           # Reproducible end-to-end training notebook
├── src/
│   └── campaignlift_ml/
│       ├── __init__.py
│       ├── data.py                  # Dataset loader, partition splits & anti-leakage guards
│       ├── baseline.py              # Propensity baselines (Logistic B0, LightGBM B1)
│       ├── uplift.py                # Causal learners (Logistic T-Learner, LightGBM T/S-Learners)
│       ├── metrics.py               # Qini curve, AUUC, and cumulative incremental gains
│       ├── compare.py               # Commercial comparison: Random vs Propensity vs Uplift
│       ├── report.py                # Slice fairness evaluation with 30/30 sample support
│       └── artifact.py              # Model serialization (model.joblib, metadata.json)
├── tests/
│   ├── test_data.py                 # Dataset loading and partition isolation tests
│   ├── test_baseline.py             # Propensity baseline behavior and probability calibration
│   ├── test_uplift.py               # T-Learner and S-Learner uplift estimation tests
│   ├── test_metrics.py              # Qini and AUUC mathematical correctness tests
│   ├── test_compare.py              # Commercial strategy comparison matrix tests
│   ├── test_report.py               # Demographic and behavioral slicing tests
│   ├── test_selection.py            # Model selection tournament logic tests
│   └── test_artifact.py             # Artifact packaging and feature schema tests
├── requirements.txt                 # Pinned Python ML dependencies
└── README.md                        # Machine learning subsystem documentation
```

---

## 3. Model Architecture & Candidate Tournament

CampaignLift evaluates five candidate models across baseline propensity and causal uplift families:

| Candidate ID | Model Family | Algorithm | Formulation | Role |
| :---: | :--- | :--- | :--- | :--- |
| **B0** | Response Baseline | Logistic Regression | $P(Y=1 \mid X)$ | Linear propensity baseline |
| **B1** | Response Baseline | LightGBM Classifier | $P(Y=1 \mid X)$ | Non-linear propensity baseline |
| **U0** | Causal T-Learner | Dual Logistic Regressions | $\tau(X) = M_1(X) - M_0(X)$ | Linear two-model uplift estimator |
| **U1** | Causal T-Learner | Dual LightGBM Models | $\tau(X) = M_1(X) - M_0(X)$ | Non-linear two-model uplift estimator |
| **U2** | **Causal S-Learner** | **LightGBM Classifier** | $\tau(X) = M(X, 1) - M(X, 0)$ | **Selected Winning Model** |

### Winning Candidate: LightGBM S-Learner (U2)
The production model utilizes a single unified LightGBM estimator trained with explicit treatment interaction features:
$$Y \sim f(X, W, X \times W)$$
where $X$ represents customer attributes and $W \in \{0, 1\}$ represents the treatment assignment.

**Why the S-Learner Won**:
- **Sample Efficiency**: Leverages the entire training cohort jointly, improving parameter sharing across control and treatment subsets.
- **Superior Qini Metric**: Outperformed T-Learners in validation AUUC and top-decile lift concentration without bifurcated variance.
- **Single-Model Serving Footprint**: Minimizes memory usage and inference latency within the FastAPI container.

---

## 4. Evaluation Metrics & Fairness Guards

### Qini Curve & AUUC
Uplift models are evaluated against randomized and propensity benchmarks:
- **Qini Curve**: Cumulative incremental transaction gain plotted as a function of targeted customer fraction:
  $$Q(f) = n_{t, 1}(f) - n_{c, 1}(f) \cdot \frac{N_t}{N_c}$$
- **AUUC (Area Under Uplift Curve)**: Normalized integral under the cumulative gains curve measuring ranking discrimination.

### Demographic & Behavioral Slicing (Responsible AI)
The evaluation reporting module (`campaignlift_ml.report`) audits model performance across demographic and behavioral cohorts:
- **Demographic Slices**: `age_band`, `region_code`, `kyc_level`
- **Behavioral Slices**: `activity_band` (0, 1-4, 5+ txns), `prior_exposure_band` (0, 1-2, 3+ campaigns)
- **Strict 30/30 Sample Support Constraint**: If either the treatment or control arm contains fewer than 30 observations in a given slice, conversion estimates are withheld (`support: "insufficient"`) to prevent statistical noise.

---

## 5. Strict Anti-Leakage & Oracle Isolation

To guarantee causal integrity and prevent data leakage:
1. **Target Feature Isolation**: Potential outcome counterfactuals ($p_0, p_1, \tau$) from `hidden_uplift.json` are **strictly forbidden** from entering training matrices.
2. **Schema Verification**: The dataset loader (`campaignlift_ml.data`) validates input feature frames against `FORBIDDEN_TRAINING_COLUMNS.txt` at load time.
3. **Oracle Dataset Separation**: The ground-truth simulator file (`hidden_uplift.json`) is isolated into a separate dataset path and accessed *only* during post-selection evaluation, with metrics explicitly flagged `"label": "synthetic_oracle"`.

---

## 6. Training Pipeline Execution Flow

The training pipeline executes in 10 sequential stages:

```text
[1. Manifest Audit] ──► [2. Anti-Leakage Check] ──► [3. Partition Isolation (Train/Val)]
                                                                   │
[6. Model Selection] ◄── [5. Validation Metrics (Qini/AUUC)] ◄─── [4. Candidate Fitting]
        │
        ▼
[7. Refit Winner on Train+Val] ──► [8. Single Test Set Score] ──► [9. Oracle Evaluation]
                                                                          │
                                                                          ▼
                                                         [10. Export Artifact Package]
```

### Artifact Export Specification
The exported artifact package (`artifacts/models/<model_version>/`) deployed to the FastAPI service includes:
- `model.joblib`: Serialized LightGBM S-Learner estimator.
- `metadata.json`: Model architecture, training hyperparameters, dataset commit SHA, random seed, and evaluation metrics.
- `feature_list.json`: Ordered list of expected input features.

---

## 7. Local Development & Testing

### 1. Install Dependencies
```bash
cd ml
pip install -r requirements.txt
```

### 2. Run the ML Test Suite
```bash
# Execute from repository root
pytest ml/tests/ -v -o pythonpath=". ml/src data/src"
```

### 3. Notebook Execution
To execute the training pipeline in a notebook environment, open:
[`notebooks/kaggle_train.ipynb`](notebooks/kaggle_train.ipynb)
