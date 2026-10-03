# CampaignLift Fixture v1 (Synthetic 200-Customer Cohort)

This directory contains the canonical synthetic 200-customer test fixture and metadata.

## Critical Data Purity & Anti-Leakage Notice

`hidden_uplift.json` contains unobservable synthetic ground truth, potential outcome probabilities (`p_y_control`, `p_y_treat`), true causal uplift (`true_uplift`), and latent customer attributes (`natural_transaction_propensity`, `qr_affinity`, `price_sensitivity`, `campaign_sensitivity`, `digital_maturity`, `offer_fatigue`).

**STRICT COMPLIANCE REQUIREMENT:**
- `hidden_uplift.json` is committed ONLY as a minimal test fixture for automated leakage tests and oracle evaluation validation.
- It MUST NEVER be merged into, joined with, or exposed to training sets, feature stores, or modeling pipelines.
- Training models MUST ONLY read `features.json` or equivalent factual feature tables.
