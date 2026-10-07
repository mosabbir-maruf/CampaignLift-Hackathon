# Responsible AI & Governance

This document establishes the ethical AI principles, concrete engineering constraints, and operational safeguards within CampaignLift.

---

## 1. Privacy & Synthetic Data Isolation

- **Synthetic Data Exclusivity**: The entire development, training, and demonstration pipeline runs exclusively on synthesized customer records and transactions.
- **Zero PII**: No real customer names, phone numbers, NID numbers, bank accounts, or real MFS transaction extracts exist in the codebase, fixtures, or database.
- **LLM Context Minimization**: When querying the Gemini Copilot, only aggregated run statistics and sanitized model attribution scores are supplied. Raw historical ledgers are never exposed in prompt context.

---

## 2. Explainability & Transparent Attribution

Campaign managers must be able to understand and defend every audience selection recommendation:
- **Dual Probability Output**: Predictions present both $P(\text{treat})$ (response with offer) and $P(\text{control})$ (response without offer), accompanied by their net difference (uplift).
- **Deterministic Reason Codes**: Customers are mapped to standardized categories:
  - `incremental_candidate`: Low organic rate, substantial increase when treated.
  - `likely_without_offer`: High organic rate; incentive is largely redundant ("Sure Thing").
  - `weak_response`: Low propensity under both treated and control conditions ("Lost Cause").
  - `negative_uplift`: Treatment decreases conversion or increases attrition ("Sleeping Dog / Do Not Disturb").
- **Directional Feature Contributions**: Top behavioral drivers (e.g. prior campaign exposures, recency, 90-day transaction volume) are displayed for each scored customer.

---

## 3. Fairness Slice Evaluation

To detect and prevent algorithmic bias, CampaignLift includes slice evaluation architecture (`ml/src/campaignlift_ml/report.py`):
- **Evaluated Slices**:
  - `age_band` (e.g. 18-24, 25-34, 35-44, 45-54, 55+)
  - `region_code` (e.g. DHK, CTG, SYL, RAJ, KHU, BAR, RAN, MYM)
  - `kyc_level` (Limited vs Verified)
  - `activity_band` (0, 1-4, 5+ 30-day txns)
  - `prior_exposure_band` (0, 1-2, 3+ past campaigns)
- **Minimum Support Rule (30/30)**: Slices with fewer than 30 treated and 30 control observations are strictly suppressed (`status: "insufficient_randomized_support"`, rates set to null) to prevent misleading generalizations from small sample sizes.
- **Executed Fairness Slice Evaluation**:
  - **Evaluation Heading**: Fairness Slice Evaluation
  - **Evaluated Population**: `fixture_v1` (`cl-synth-fixture-20261006-1c11dce`), on-disk dataset in `data/fixtures/fixture_v1`
  - **Run ID**: `run_fairness_slice_fixture_v1`
  - **Row Count**: 23 rows (validation cohort from the 103 feature records on disk)
  - **Result File**: `docs/fairness_slice_evaluation.json`
  - **Execution Command**: `python -m ml.src.campaignlift_ml.report`
- **Un-evaluated Populations**:
  - The 100,000-customer benchmark did not run.
  - The ml_dev population of 25,000 customers did not run.
- **Synthetic Disclaimer**: Synthetic regional distributions reflect simulated parameters and do not represent real demographic communities.

---

## 4. Human Oversight & Operational Boundaries

- **Decision-Support Designation**: Every page in the user interface prominently displays the `"Decision support"` badge.
- **No Automated Execution**: The platform contains no button, endpoint, or background job capable of sending real marketing messages, triggering external webhooks, or disbursing funds.
- **Managerial Discretion**: High-impact recommendations explicitly state that the campaign manager retains sole authority over campaign launch, budget allocation, and target selection.

---

## 5. Transparency & Stated Limitations

The platform enforces explicit labeling across all screens:
1. **Expected vs Measured**: Expected incremental values are explicitly marked as projections under manager-supplied assumptions.
2. **Oracle Metrics**: Metrics computed against the synthetic simulator's ground-truth parameters are explicitly labeled `"label": "synthetic_oracle"` with warnings that they are unobservable in production.
3. **No Real-World Claims**: The platform explicitly disclaims that results represent real upay customers or actual commercial campaign outcomes.
