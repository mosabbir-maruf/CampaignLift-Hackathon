# Machine Learning & Uplift Methodology

CampaignLift formulates campaign audience selection as a **causal inference problem** rather than a standard propensity estimation problem.

---

## 1. The Core Questions: Response vs. Uplift

Traditional marketing platforms train a **Response Model** to answer:
$$\text{Response Question: } P(Y=1 \mid X, T=1)$$
*"Which customer has the highest probability of transacting when sent an incentive?"*

This question creates severe budget waste by disproportionately targeting **"Sure Things"**—highly active customers who would have completed the transaction regardless of the incentive.

CampaignLift trains an **Uplift Model** to answer the incremental counterfactual question:
$$\text{Uplift Question: } \tau(X) = E[Y \mid X, T=1] - E[Y \mid X, T=0] = P(Y=1 \mid X, T=1) - P(Y=1 \mid X, T=0)$$
*"For which customer does the incentive cause a positive change in transaction probability?"*

### Customer Causal Quadrants

```
                        Treated Outcome (T=1)
                       0                     1
                 ┌───────────────────┬───────────────────┐
               0 │     Lost Causes   │    Persuadables   │
                 │   (Uplift = 0)    │   (Uplift > 0)    │
Control Outcome  │   Never transact  │ TARGET AUDIENCE   │
(T=0)            ├───────────────────┼───────────────────┤
               1 │    Sleeping Dogs  │    Sure Things    │
                 │   (Uplift < 0)    │   (Uplift = 0)    │
                 │   DO NOT DISTURB  │ Transact anyway   │
                 └───────────────────┴───────────────────┘
```

---

## 2. Dataset Splitting & Strict Anti-Leakage Protocol

### Dataset Partitioning
- **Dataset Version**: `cl-synth-ml_dev-20261006-8ad556a`
- **Splits**: 60% Train, 20% Validation, 20% Test (stratified by treatment arm and target outcome).
- **Global Seed**: `20261006`

### Anti-Leakage Governance
All feature tables and dataset partitions pass automated leakage verification (`data/src/campaignlift_data/validate.py`):
1. **Temporal Cutoff**: All historical transactions used for feature aggregation must satisfy `timestamp < campaign_assigned_at`. Zero future transactions are allowed into feature matrices.
2. **Forbidden Column Rejection**: Columns representing hidden causal states (`true_uplift`, `latent_profile`, `campaign_sensitivity`, `p_y_treat`, `p_y_control`) are strictly rejected by the data loader (`assert_no_forbidden_columns`).
3. **Single Test Evaluation**: Candidate selection is performed strictly on the validation set. The test split is evaluated exactly once after candidate freeze.

---

## 3. Model Candidates & Selection Rule

We evaluated four candidate architectures:
- **Baseline (B0)**: Logistic Regression Response Model (predicts $P(Y=1 \mid X, T=1)$ only).
- **Candidate U0**: Logistic T-Learner (interpretable fallback with separate treated and control models).
- **Candidate U1**: LightGBM T-Learner (separate gradient-boosted trees for treated and control arms).
- **Candidate U2**: LightGBM S-Learner (single gradient-boosted tree with treatment indicator and interaction features).

### Selection Rule
Rank candidates by validation Qini score. If the top candidate is LightGBM, select the simpler Logistic T-Learner if the difference in normalized Qini is $< 0.01$.

---

## 4. Measured Evaluation Metrics

All metrics reported below are copied directly from verified JSON run outputs (`validation_metrics.json` and `test_metrics.json`). No metrics are extrapolated or fabricated.

### Validation Set Performance (`validation_metrics.json`)
- **Winning Candidate**: `U2` (LightGBM S-Learner)
- **Model Version**: `cl-model-ml_dev_20261006-lgbm_s_learner-r01`
- **Fit Time**: 0.057s
- **Validation Qini Score**: `48.4578`
- **Normalized Qini (AUUC)**: `0.1342`
- **Top 10% Incremental Rate**: `0.1863` (18.6% incremental conversion rate in top decile)
- **Mean Predicted Uplift**: `0.0054`
- **Average Treatment Effect (ATE)**: `-0.0198`
- **Constraint Check**: Passed all minimum support and convergence constraints.

### Test Set Performance (`test_metrics.json`)
- **Evaluation Cohort Size**: $N = 2,530$
- **Test Qini Score**: `65.2257`
- **Test Normalized Qini (AUUC)**: `0.1755`
- **Test Top 10% Incremental Rate**: `0.1873` (18.7% incremental conversion rate in top decile)
- **Test ATE**: `-0.0076`
- **Mean Predicted Uplift**: `-0.0046`
- **Standard Deviation of Uplift**: `0.0768`

---

## 5. Segment Fairness & Support Rules

Evaluation across demographic and behavioral slices (`ml/src/campaignlift_ml/report.py`):
- **Slices**: `age_band`, `region_code`, `kyc_level`, `activity_band` (0, 1-4, 5+ txns), `prior_exposure_band` (0, 1-2, 3+ campaigns).
- **Minimum Support Threshold**: Slices with $< 30$ observations in either treatment or control arm are nulled (`support: "insufficient"`) to prevent statistical hallucination on small sample sizes.
- **Full Benchmark Evaluation**: Per Decision D-024, full 100k benchmark slice reporting is marked **NOT YET EVALUATED** for local workstation environments.
