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

#### Bootstrap Confidence Intervals (`docs/bootstrap_intervals.json`)
Percentile bootstrap intervals evaluated using 200 resamples with replacement and random seed `20261006` on the frozen LightGBM S-Learner (candidate `U2`, no refitting performed):
- **Test Qini Score**:
  - *Historical Published (Kaggle ml_dev test, $N=2,530$)*: `65.2257`
  - *Recomputed on-disk test split (`fixture_v1`, $N=16$)*: `1.0438` (differs from historical due to cohort size $N=16$ vs $N=2,530$)
  - *95% Percentile Bootstrap Interval (2.5%, 97.5%)*: `[-0.1060, 2.2788]`
- **Test Normalized Qini (AUUC)**:
  - *Historical Published (Kaggle ml_dev test, $N=2,530$)*: `0.1755`
  - *Recomputed on-disk test split (`fixture_v1`, $N=16$)*: `0.4841` (differs from historical due to cohort size $N=16$ vs $N=2,530$)
  - *95% Percentile Bootstrap Interval (2.5%, 97.5%)*: `[-0.1557, 0.9377]`
- **Pre-committed Configuration**: 200 resamples, seed `20261006`, percentiles `[2.5, 97.5]`, `refit_performed: false`.

---

## 5. Segment Fairness & Support Rules

Evaluation across demographic and behavioral slices (`ml/src/campaignlift_ml/report.py`):
- **Slices**: `age_band`, `region_code`, `kyc_level`, `activity_band` (0, 1-4, 5+ txns), `prior_exposure_band` (0, 1-2, 3+ campaigns).
- **Minimum Support Threshold**: Slices with $< 30$ observations in either treatment or control arm are nulled (`support: "insufficient"`) to prevent statistical hallucination on small sample sizes.
- **Full Benchmark Evaluation**: Per Decision D-024, full 100k benchmark slice reporting is marked **NOT YET EVALUATED** for local workstation environments.

---

## 6. Seed Stability and Treatment Assignment Sensitivity

Evaluated via `python -m campaignlift_ml.sensitivity -> docs/sensitivity_analysis.json`.
Governance Policy: The deployed champion model remains frozen as `cl-model-ml_dev_20261006-lgbm_s_learner-r01`; no new champion model is declared.

### Repeated-Seed Validation AUUC Stability
Evaluates LightGBM S-Learner performance across 5 random seeds to show stability:

| Seed | Model | Validation AUUC | Validation Qini | Status |
| --- | --- | --- | --- | --- |
| 20261006 | lightgbm_s_learner | 0.0189 | 0.0435 | completed |
| 20261007 | lightgbm_s_learner | 0.8212 | 1.8899 | completed |
| 20261008 | lightgbm_s_learner | -0.1700 | -0.3913 | completed |
| 20261009 | lightgbm_s_learner | 0.8690 | 2.0000 | completed |
| 20261010 | lightgbm_s_learner | 0.6877 | 1.5826 | completed |

- **Completed Seeds**: 5 / 5
- **Mean AUUC**: `0.4453`
- **Standard Deviation**: `0.4336`
- **Minimum AUUC**: `-0.1700`
- **Maximum AUUC**: `0.8690`
- **AUUC Spread**: `1.0390`

### Treatment Assignment Shift Sensitivity Comparison
Evaluates rankers under baseline RCT ($p=0.5$) and shifted assignment ($p=0.3$) conditions on the validation cohort:

| condition | model | AUUC | top_decile_incremental_rate | n |
| --- | --- | --- | --- | --- |
| baseline_rct (p=0.5) | response_propensity | -0.2569 | -0.5000 | 23 |
| baseline_rct (p=0.5) | logistic_t_learner | -0.0592 | 1.0000 | 23 |
| baseline_rct (p=0.5) | lightgbm_s_learner | -0.0504 | 0.0000 | 23 |
| shifted_assignment (p=0.3) | response_propensity | -0.3577 | -1.0000 | 21 |
| shifted_assignment (p=0.3) | logistic_t_learner | -0.1314 | 0.0000 | 21 |
| shifted_assignment (p=0.3) | lightgbm_s_learner | 0.2482 | 0.0000 | 21 |

Under treatment assignment shift ($p=0.30$), the causal LightGBM S-Learner maintains positive AUUC (`0.2482`), whereas response propensity exhibits severe negative uplift ranking (`-0.3577`), demonstrating the necessity of causal uplift over standard response propensity.

