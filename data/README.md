# CampaignLift Synthetic Data Generation & Release Pipeline

> **Synthetic World Disclaimer:**
> The entire CampaignLift data ecosystem—including customer entities, historical transactions, campaign interactions, potential outcomes, and true causal uplift—is completely synthetic. It was engineered using causal DAG simulation algorithms for the AI Dev Fest 2026 Hackathon. It does not contain, derive from, or reflect real upay customer accounts, confidential records, or PII. No claims regarding real upay customers or commercial operations are made.

---

## 1. Quickstart & Generator Commands

The causal pipeline supports reproducible dataset generation across multiple cohort scales. To generate and validate datasets locally:

```bash
# Generate and validate test fixture (200 customers, committed)
python -m campaignlift_data.generate --config data/config/world.yaml --profile fixture

# Generate and validate development dataset (5,000 customers, untracked)
python -m campaignlift_data.generate --config data/config/world.yaml --profile dev

# Generate and validate ML development dataset (25,000 customers, untracked)
python -m campaignlift_data.generate --config data/config/world.yaml --profile ml_dev

# Validate any generated dataset release directory
python -m campaignlift_data.validate data/generated/ml_dev
```

---

## 2. Seed Architecture & Deterministic Derivation

All generator stages derive their pseudorandom seeds hierarchically from a single `global_seed` defined in `data/config/world.yaml`.

- **Global Seed:** `20261006` (Changing this seed produces a distinct versioned synthetic world).
- **Stage Offsets:** To guarantee statistical independence between generation phases without cross-stage contamination, stage seeds use fixed integer offsets:

| Stage | Config Key | Offset | Resolved Seed | Functional Role |
| :--- | :--- | :---: | :---: | :--- |
| `customers` | `stage_seeds.customers` | `+1` | `20261007` | Customer demographics and 4 latent causal profile mixture weights |
| `transactions` | `stage_seeds.transactions` | `+2` | `20261008` | Poisson event timing and lognormal spending amount distributions |
| `prior_exposures` | `stage_seeds.prior_exposures`| `+3` | `20261009` | Historical campaign interactions generating offer fatigue |
| `treatment_assignment` | `stage_seeds.treatment_assignment`| `+4` | `20261010` | Strict 50/50 randomized controlled trial (RCT) treatment draw |
| `outcome_simulation` | `stage_seeds.outcome_noise_and_bernoulli`| `+5` | `20261011` | Counterfactual potential outcomes and factual Bernoulli draws |
| `split` | `stage_seeds.split` | `+6` | `20261012` | Deterministic hash partition into train (60%), val (20%), test (20%) |

---

## 3. Schemas & Table Architecture

The synthetic release pipeline produces 8 standardized data tables documented in [`docs/data_dictionary.md`](file:///d:/AI%20Dev%20Fest%20with%20bros/CampaignLift-Internal/docs/data_dictionary.md) and validated against JSON Schemas in `data/schemas/`:

1. **`customers.json`** (`customer.schema.json`): Static customer demographics (age band, region, KYC verification level, acquisition channel).
2. **`transactions.json`** (`transaction.schema.json`): Pre-assignment transaction history over the 90-day baseline window.
3. **`campaign.json`** (`campaign.schema.json`): Target campaign metadata (objective, offer type, incentive value, cost).
4. **`exposures.json`** (`exposure.schema.json`): Randomized treatment assignment records with true assignment propensity ($e=0.5$).
5. **`outcomes.json`** (`outcome.schema.json`): Factual 14-day evaluation window transaction indicator ($Y \in \{0, 1\}$) and window spend.
6. **`features.json`** (`feature_table.schema.json`): Production ML training feature table combining pre-assignment behavior and campaign attributes.
7. **`splits.json`** (`manifest.schema.json`): Deterministic customer split assignments (`train`, `val`, `test`).
8. **`hidden_uplift.json`** (`hidden_uplift.schema.json`): Unobservable ground truth potential outcomes ($p_0, p_1$), individual treatment effect ($\tau = p_1 - p_0$), and latent causal attributes.

---

## 4. Anti-Leakage Rules & Strict Separation

To maintain absolute causal and temporal validity, the pipeline enforces strict release blockers in `validate.py`:

- **Forbidden Column Intersect:** The training feature table (`features.json`) is cryptographically scanned against `data/schemas/FORBIDDEN_TRAINING_COLUMNS.txt`. Any presence of unobservable latent variables (`natural_transaction_propensity`, `qr_affinity`, `price_sensitivity`, `campaign_sensitivity`, `digital_maturity`, `offer_fatigue`) or oracle ground truth (`p_y_control`, `p_y_treat`, `true_uplift`) immediately fails validation with exit code 1.
- **Strict Temporal Precedence:** Historical transactions used to construct pre-assignment features must strictly precede campaign assignment: $\max(t_{\text{txn}}) < t_{\text{assigned\_at}}$.
- **Directory Isolation:** The synthetic oracle ground truth (`hidden_uplift.json`) must never be placed inside the `features/` directory or joined into model inputs.

---

## 5. Design Targets vs. Measured Validation Results

All empirical measurements below are sourced directly from verified test run reports (`data/reports/validation_report.json`, `data/reports/validation_report_dev.json`, `data/reports/validation_report_ml_dev.json`) and release manifests:

| Quality Check / Metric | Source Verification | Design Target | Fixture (`fixture_v1`) | Development (`dev`) | ML-Dev (`ml_dev`) | Benchmark (`benchmark`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Customers** | manifest `row_counts` | Config size | 200 | 5,000 | 25,000 | NOT YET EVALUATED |
| **Historical Transactions** | manifest `row_counts` | ~20–25 / active | 3,964 | 101,640 | 509,244 | NOT YET EVALUATED |
| **Eligible Exposures** | manifest `row_counts` | ~50% cohort | 103 (51.50%) | 2,518 (50.36%) | 12,491 (49.96%) | NOT YET EVALUATED |
| **Empirical Treatment Rate**| manifest `treatment_rate` | `[0.45, 0.55]` | 0.4757 (49/103) | 0.5032 (1267/2518) | 0.4953 (6187/12491) | NOT YET EVALUATED |
| **Negative Uplift ($\tau < 0$)** | validation report | `> 0` mass | 50 (25.00%) | 1,260 (25.20%) | 6,197 (24.79%) | NOT YET EVALUATED |
| **Positive Uplift ($\tau > 0.02$)**| validation report | `> 0` contrast | 143 (71.50%) | 3,572 (71.44%) | 18,304 (73.22%) | NOT YET EVALUATED |
| **Outcome Base Rate ($y=1$)** | validation report | `[0.02, 0.80]` | 0.5437 (56/103) | 0.5485 (1381/2518) | 0.5996 (7489/12491) | NOT YET EVALUATED |
| **Feature Sparsity (>95% zeros)** | validation report | 0 features | 0 features | 0 features | 0 features | NOT YET EVALUATED |
| **Forbidden Training Columns** | validation report | 0 leaked | 0 leaked | 0 leaked | 0 leaked | NOT YET EVALUATED |
| **Temporal Future Events** | validation report | 0 future events | 0 future events | 0 future events | 0 future events | NOT YET EVALUATED |
| **Validator Exit Code** | `validate.py` CLI | `0` (Passed) | `0` (34/34 passed) | `0` (34/34 passed) | `0` (34/34 passed) | NOT YET EVALUATED |
