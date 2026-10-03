# CampaignLift Synthetic Data Dictionary

> **Synthetic Data Disclaimer:**
> All data within the CampaignLift repository, including customer profiles, transactions, campaign interactions, and uplift outcomes, is entirely synthetic. It was generated via causal simulation algorithms for the AI Dev Fest 2026 Hackathon. It does not represent, contain, or extrapolate from real upay customer data, PII, or actual production metrics. No commercial or marketing claims about upay customers are made or implied.

---

## 1. Overview of Synthetic World Tables

The CampaignLift data pipeline models a randomized controlled trial (A/B test) for fintech marketing campaign optimization. The data is partitioned into observed operational tables, training feature tables, and an unobservable synthetic oracle table.

| File Name | Domain | Primary Key | Foreign Keys | Scope |
| :--- | :--- | :--- | :--- | :--- |
| `customers.json` | Static customer demographics | `customer_id` | - | All customers |
| `transactions.json` | 90-day pre-assignment history | `transaction_id` | `customer_id` | All customer txns |
| `campaign.json` | Campaign metadata & parameters | `campaign_id` | - | Modeled campaign |
| `exposures.json` | 50/50 RCT treatment assignment | `exposure_id` | `customer_id`, `campaign_id` | Eligible cohort |
| `outcomes.json` | 14-day post-assignment factual outcomes | `customer_id` | `customer_id`, `campaign_id` | Eligible cohort |
| `features.json` | ML feature store for training | `customer_id` | `customer_id`, `campaign_id` | Eligible cohort |
| `splits.json` | Deterministic cohort splits (60/20/20) | `customer_id` | `customer_id` | All customers |
| `hidden_uplift.json` | Synthetic causal oracle ground truth | `customer_id` | `customer_id`, `campaign_id` | Unobservable truth |
| `manifest.json` | Release checksums & audit record | `dataset_version` | - | Dataset release metadata |

---

## 2. Pre-Assignment Feature Table (`features.json`)

The feature table contains strictly pre-assignment historical metrics and campaign offer attributes. All 26 fields in `feature_table.schema.json` are documented below:

| Column Name | Type | Nullable | Domain / Constraints | Description & Calculation Rule |
| :--- | :--- | :---: | :--- | :--- |
| `customer_id` | string | No | `^C[0-9]{8}$` | Unique customer identifier (e.g. `C00000001`). Foreign key to `customers.json`. |
| `campaign_id` | string | No | Non-empty string | Target campaign identifier (e.g. `CMP2024_QR01`). |
| `tenure_days` | integer | No | `>= 0` | Account age in days from signup to campaign assignment time. |
| `age_band` | string | No | `18-24`, `25-34`, `35-44`, `45-54`, `55+` | Demographic age bracket of the customer. |
| `region_code` | string | No | `DHK`, `CTG`, `SYL`, `RAJ`, `KHU`, `BAR`, `RAN`, `MYM` | Administrative division of Bangladesh where account is registered. |
| `kyc_level` | string | No | `limited`, `verified` | Account verification status per regulatory framework. |
| `acquisition_channel`| string | No | `app`, `agent`, `referral` | Customer onboarding source channel. |
| `txn_count_30d` | integer | No | `>= 0` | Number of completed transactions in the 30 days prior to assignment. |
| `txn_count_90d` | integer | No | `>= 0` | Number of completed transactions in the 90 days prior to assignment (`>= txn_count_30d`). |
| `txn_amount_30d_bdt`| number | No | `>= 0.0` | Total transaction volume in BDT across prior 30 days. |
| `txn_amount_90d_bdt`| number | No | `>= 0.0` | Total transaction volume in BDT across prior 90 days (`>= txn_amount_30d_bdt`). |
| `qr_txn_share_90d` | number | No | `[0.0, 1.0]` | Share of QR merchant payments: `qr_txn_count_90d / max(txn_count_90d, 1)`. |
| `cashout_share_90d` | number | No | `[0.0, 1.0]` | Share of cash-out transactions: `cashout_count_90d / max(txn_count_90d, 1)`. |
| `merchant_pay_share_90d`| number | No | `[0.0, 1.0]` | Share of merchant payments: `merchant_count_90d / max(txn_count_90d, 1)`. |
| `days_since_last_txn`| integer | No | `>= 0` | Days elapsed since most recent transaction prior to assignment. Defaults to `999` if inactive. |
| `avg_ticket_90d_bdt`| number | No | `>= 0.0` | Average transaction ticket: `txn_amount_90d_bdt / max(txn_count_90d, 1)`. |
| `app_channel_share_90d`| number| No | `[0.0, 1.0]` | Share of transactions initiated via the mobile app vs agent/USSD: `app_count_90d / max(txn_count_90d, 1)`. |
| `campaign_exposures_prior_30d`| integer| No| `>= 0` | Marketing campaigns targeted to this customer in the prior 30 days. |
| `campaign_exposures_prior_90d`| integer| No| `>= 0` | Marketing campaigns targeted to this customer in the prior 90 days (`>= prior_30d`). |
| `days_since_last_campaign`| integer| No| `>= 0` | Days elapsed since prior campaign touchpoint. Defaults to `999` if no prior exposure. |
| `objective` | string | No | `activation`, `qr_adoption`, `reactivation`, `retention` | Marketing campaign strategic objective. |
| `offer_type` | string | No | `flat_cashback`, `pct_cashback`, `fee_waiver` | Incentive reward structure offered to treated customers. |
| `incentive_value` | number | No | `>= 0.0` | Nominal reward value (e.g. `20.0` BDT for flat cashback). |
| `incentive_cost_bdt`| number | No | `>= 0.0` | Expected financial budget cost in BDT per treated customer. |
| `treatment` | integer | No | `0, 1` | Randomized treatment indicator: `1` = treated (received offer), `0` = control (no offer). |
| `y_transacted` | integer | No | `0, 1` | Factual observed conversion in the 14-day post-assignment evaluation window. |

---

## 3. Operational Tables

### 3.1 `customers.json`
- `customer_id` (string): Unique identifier matching regex `^C[0-9]{8}$`.
- `signup_date` (string, ISO date): Account creation date prior to historical observation window.
- `age_band` (enum): `18-24`, `25-34`, `35-44`, `45-54`, `55+`.
- `region_code` (enum): `DHK`, `CTG`, `SYL`, `RAJ`, `KHU`, `BAR`, `RAN`, `MYM`.
- `kyc_level` (enum): `limited`, `verified`.
- `acquisition_channel` (enum): `app`, `agent`, `referral`.

### 3.2 `transactions.json`
- `transaction_id` (string): Unique transaction ID matching regex `^TXN[0-9]{10}$`.
- `customer_id` (string): Reference to `customers.json`.
- `event_time` (string, ISO datetime): Strictly `< campaign.start_date` for pre-assignment history.
- `txn_type` (enum): `p2p_transfer`, `p2p_receive`, `cash_in`, `cash_out`, `merchant_pay`, `airtime`, `utility_bill`.
- `amount_bdt` (number): Transaction value in BDT. Must be strictly `> 0.0`.
- `channel` (enum): `app`, `ussd`, `agent`, `qr`.
- `merchant_category` (string, nullable): Category if merchant transaction (`groceries`, `pharmacy`, etc.), null otherwise.
- `direction` (enum): `in`, `out`.

### 3.3 `campaign.json`
- `campaign_id` (string): Unique campaign identifier (`CMP2024_QR01`).
- `campaign_name` (string): Human-readable campaign title.
- `objective` (enum): `activation`, `qr_adoption`, `reactivation`, `retention`.
- `offer_type` (enum): `flat_cashback`, `pct_cashback`, `fee_waiver`.
- `incentive_value` (number): Value of incentive.
- `incentive_cost_bdt` (number): Cost per customer treated.
- `channel` (string): Delivery channel (`in_app`).
- `start_date` (string, ISO date): Launch date (`2024-02-01`).
- `end_date` (string, ISO date): Conclusion date (`2024-02-14`).
- `outcome_window_days` (integer): Evaluation horizon (strictly `14` days).

### 3.4 `exposures.json`
- `exposure_id` (string): Unique record ID.
- `customer_id` (string): Reference to eligible customer.
- `campaign_id` (string): Reference to campaign.
- `eligible` (boolean): Eligibility indicator (strictly `true`).
- `treatment` (integer): Randomized 50/50 assignment (`0` or `1`).
- `assignment_probability` (number): Known true propensity (strictly `0.5`).
- `assigned_at` (string, ISO datetime): Exact campaign assignment timestamp (`2024-02-01T00:00:00Z`).

### 3.5 `outcomes.json`
- `customer_id` (string): Reference to exposed customer.
- `campaign_id` (string): Reference to campaign.
- `y_transacted` (integer): `1` if transacted in 14-day window, `0` otherwise.
- `txn_count_window` (integer): Count of transactions in evaluation window (`0` if `y=0`, `>= 1` if `y=1`).
- `txn_amount_window_bdt` (number): Total transaction amount in window (`0.0` if `y=0`, `> 0.0` if `y=1`).
- `window_start` (string, ISO datetime): Start of 14-day outcome window (`assigned_at`).
- `window_end` (string, ISO datetime): End of 14-day outcome window (`assigned_at + 14 days`).

### 3.6 `splits.json`
- `customer_id` (string): Reference to customer.
- `split` (enum): `train` (60%), `val` (20%), `test` (20%). Deterministic assignment via sha256 hash modulo 100.

---

## 4. Synthetic Causal Ground Truth (`hidden_uplift.json`)

`hidden_uplift.json` contains unobservable counterfactual potential outcomes and latent customer propensities. It is generated strictly for offline evaluation and benchmark verification.

> **CRITICAL ANTI-LEAKAGE ENFORCEMENT:**
> Under no circumstances may any column in `hidden_uplift.json` appear in `features.json` or model training pipelines.

| Column Name | Type | Range / Domain | Definition & Causal Simulation Rule |
| :--- | :--- | :--- | :--- |
| `customer_id` | string | `^C[0-9]{8}$` | Customer identifier matching operational tables. |
| `campaign_id` | string | Non-empty string | Modeled campaign identifier. |
| `p_y_control` | number | `[0.01, 0.99]` | Baseline conversion probability under control: $p_0 = \sigma(\text{logit}_0)$. |
| `p_y_treat` | number | `[0.01, 0.99]` | Treatment conversion probability: $p_1 = \sigma(\text{logit}_1)$. |
| `true_uplift` | number | `[-0.98, 0.98]` | True individual causal uplift: $\tau_i = p_1 - p_0$. |
| `natural_transaction_propensity` | number | `[0.0, 1.0]` | Latent intrinsic baseline likelihood to transact without marketing. |
| `qr_affinity` | number | `[0.0, 1.0]` | Latent inclination to adopt QR payments. |
| `price_sensitivity` | number | `[0.0, 1.0]` | Responsiveness to discount / cashback monetary magnitude. |
| `campaign_sensitivity` | number | `[0.0, 1.0]` | General persuadability / responsiveness to promotional messaging. |
| `digital_maturity` | number | `[0.0, 1.0]` | Latent proficiency and app feature adoption level. |
| `offer_fatigue` | number | `[0.0, 1.0]` | Saturation penalty derived from historical campaign exposure frequency. |

---

## 5. Design Targets vs. Measured Validation Metrics

All empirical values below are extracted directly from verified validation reports and manifests.

| Metric | Source File | Design Target / Rule | Measured `fixture_v1` (200) | Measured `dev` (5,000) | Measured `ml_dev` (25,000) | Measured `benchmark` (100,000) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Customers** | manifest row_counts | Population size | 200 | 5,000 | 25,000 | NOT YET EVALUATED |
| **Historical Transactions** | manifest row_counts | ~20–25 / active cust | 3,964 | 101,640 | 509,244 | NOT YET EVALUATED |
| **Eligible Exposures** | manifest row_counts | 40%–60% of population | 103 (51.50%) | 2,518 (50.36%) | 12,491 (49.96%) | NOT YET EVALUATED |
| **Empirical Treatment Rate**| manifest treatment_rate | `[0.45, 0.55]` | 0.4757 (49/103) | 0.5032 (1267/2518) | 0.4953 (6187/12491) | NOT YET EVALUATED |
| **Negative Uplift Mass ($\tau < 0$)** | validation_report.json | `> 0` customers | 50 (25.00%) | 1,260 (25.20%) | 6,197 (24.79%) | NOT YET EVALUATED |
| **Positive Uplift ($\tau > 0.02$)** | validation_report.json | `> 0` customers | 143 (71.50%) | 3,572 (71.44%) | 18,304 (73.22%) | NOT YET EVALUATED |
| **Outcome Base Rate ($y=1$)** | validation_report.json | `[0.02, 0.80]` | 0.5437 (56/103) | 0.5485 (1381/2518) | 0.5996 (7489/12491) | NOT YET EVALUATED |
| **Feature Sparsity (>95% zeros)** | validation_report.json | 0 sparse features | 0 features | 0 features | 0 features | NOT YET EVALUATED |
| **Forbidden Training Columns** | validation_report.json | 0 leaked columns | 0 leaked | 0 leaked | 0 leaked | NOT YET EVALUATED |
| **Temporal Future Events** | validation_report.json | 0 future events | 0 future events | 0 future events | 0 future events | NOT YET EVALUATED |
| **Validation Suite Status** | manifest / report | `passed` (34/34 checks)| `PASSED` | `PASSED` | `PASSED` | NOT YET EVALUATED |
