# CampaignLift: Project Report Draft

**Track**: Track 04 — Growth & Campaign Intelligence  
**Team**: CampaignLift (Assaduzzaman, Mosabbir, Anik)  
**Date**: October 2026  
**Status**: Ready for Submission Review  

---

## 1. User & Problem Statement

Mobile Financial Services (MFS) in emerging economies (such as Bangladesh) spend millions of BDT annually on user acquisition, merchant payments, and QR adoption campaigns. Campaign managers face two persistent challenges:
1. **Inefficient Budget Allocation**: Campaign budgets are allocated by targeting users with high predicted transaction propensity (e.g. active users likely to send money or make merchant payments).
2. **Incentive Wastage & Customer Fatigue**: A large portion of campaign budget is spent incentivizing customers who would have completed the transaction anyway ("Sure Things"), while over-messaging other segments causes campaign fatigue and churn ("Sleeping Dogs").

CampaignLift is an AI-powered incremental campaign decision engine designed to solve this problem by helping campaign managers answer: **"Which customer transactions will happen ONLY IF we spend this incentive?"**

---

## 2. Why Response Targeting is the Wrong Question

Standard predictive marketing workflows optimize for the **Response Question**:
$$\max P(\text{Transact} \mid \text{Offer})$$

This creates severe commercial distortions:
- **Conflation of Propensity and Incrementality**: High-volume users have an 80% natural transaction probability. Giving them a 50 BDT cashback incentive yields an 82% transaction probability—an incremental lift of just +2%. Yet a response model gives them top ranking, taking credit for transactions that were already going to happen.
- **Negative Treatment Effects Ignored**: Unsolicited promotional messages can irritate dormant users or prompt churn. Response models never penalize this adverse reaction.
- **Causal Uplift Formulation**:
  $$\text{Uplift } \tau(X) = P(\text{Transact} \mid X, \text{Offer}) - P(\text{Transact} \mid X, \text{No Offer})$$
  CampaignLift isolates the **"Persuadables"** (high $\tau$) from the **"Sure Things"** (high propensity, near-zero $\tau$) and **"Sleeping Dogs"** ($\tau < 0$).

---

## 3. What Was Built

CampaignLift delivers an end-to-end, production-grade decision-support workstation:
1. **FastAPI Causal Decision Engine**: Modular backend service executing causal inference, greedy knapsack budget allocation, and feature attribution.
2. **Containerized Edge Topology**: Nginx Alpine reverse proxy container serving static assets with gzip compression, routing API and healthcheck traffic, and keeping backend internal ports isolated.
3. **React 19 / TypeScript Analytics Workstation**: 8 interactive decision-support views (Campaign Setup, Audience Explorer, Uplift Distribution, Strategy Comparison, Budget Allocation Curves, Feature Attribution, and Copilot).
4. **Grounded Gemini Copilot**: AI campaign assistant locked to verified run JSON context, refusing hallucinations and resisting prompt injection.
5. **Synthetic Data & Experiment Simulator**: Realistic MFS history generator with zero data leakage.

---

## 4. Synthetic Data & Its Limits

- **Data Generator Architecture**: Simulates 25,000 customers, 500,000+ transactions, customer tenure, merchant category distributions, app vs. agent channel affinities, and past campaign exposure fatigue.
- **Leakage Prevention**: All features are computed strictly prior to assignment timestamps (`timestamp < assigned_at`). Hidden causal parameters are barred from feature tables via schema assertion gates.
- **Known Limitations**:
  - Synthetic data reflects parameterized behavioral distributions rather than real Bangladeshi macroeconomic trends.
  - The simulator's randomized trial is artificial and must be re-validated on governed commercial data before operational deployment.

---

## 5. Model Evaluation (Measured Metrics Only)

Model selection was conducted across candidate architectures (Logistic Baseline, Logistic T-Learner, LightGBM T-Learner, LightGBM S-Learner) on a 60/20/20 train/validation/test split ($N = 2,530$ on test split).

### Measured Performance Summary (from `validation_metrics.json` & `test_metrics.json`):
| Metric | Validation Set | Test Set (Single Final Look) |
| :--- | :---: | :---: |
| **Winning Architecture** | LightGBM S-Learner (`U2`) | LightGBM S-Learner (`U2`) |
| **Model Version** | `cl-model-ml_dev_20261006-lgbm_s_learner-r01` | `cl-model-ml_dev_20261006-lgbm_s_learner-r01` |
| **Qini Score** | `48.4578` | `65.2257` |
| **Normalized Qini (AUUC)** | `0.1342` | `0.1755` |
| **Top 10% Incremental Rate** | `0.1863` (+18.6% lift) | `0.1873` (+18.7% lift) |
| **Average Treatment Effect (ATE)** | `-0.0198` | `-0.0076` |
| **Inference Fit Time** | 0.057s | — |

The LightGBM S-Learner achieved superior AUUC performance by capturing non-linear interactions between prior campaign fatigue, transaction recency, and incentive unit value.

---

## 6. Product Walkthrough

1. **Campaign Creation**: Manager enters campaign objective, offer type, and budget limits.
2. **Inference & Scoring**: The engine evaluates the customer base, computing treatment and control probabilities and assigning uplift ranks.
3. **Strategy Comparison**: The decision matrix contrasts Random, Response, and Uplift strategies. In live testing, response targeting selected **40% negative-uplift customers**, whereas the Uplift model enforced **0%**.
4. **Budget Knapsack Optimizer**: Allocates budget to maximize total incremental transaction value under user-defined constraints.
5. **Customer Explanations**: Provides feature waterfall contributions and plain-language reason codes (`incremental_candidate`, `likely_without_offer`, etc.).
6. **Gemini Copilot**: Assists managers with grounded scenario interpretation based strictly on verified run context.

---

## 7. Responsible AI & Governance

- **Human Oversight**: The platform is strictly advisory; no automated outbound messages or financial disbursements are permitted.
- **Slice Fairness**: Slices across age, region, KYC tier, and transaction frequency enforce a 30/30 minimum randomized support rule to prevent small-sample bias.
- **Labeling & Transparency**: Projected incremental values are clearly marked as expected under assumed manager parameters.

---

## 8. Requirements for Real-World Deployment

Before deploying CampaignLift in an active banking or MFS production environment:
1. **Governed Data Warehouse Ingestion**: Replace synthetic data tables with secured, PII-tokenized MFS data warehouse extracts (e.g. Snowflake / BigQuery).
2. **A/B Holdout Trial Integration**: Calibrate uplift models on true randomized holdouts (e.g. 10% control group) running on live campaigns.
3. **Regulatory Compliance**: Integrate audit trails for Bangladesh Bank compliance and consumer data protection regulations.
