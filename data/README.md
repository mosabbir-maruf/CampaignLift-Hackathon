# CampaignLift Synthetic Data Generation & Release Pipeline

This directory contains the synthetic causal data generation pipeline, world simulation configurations, observed/hidden schemas, automated release manifests, validation suites, and test fixtures for the CampaignLift Uplift Modeling & Campaign Optimization System.

---

## Generator Command

To generate and validate synthetic dataset cohorts locally, execute the generation runner with the designated profile:

```bash
# Generate and validate development dataset (5,000 customers)
python -m campaignlift_data.generate --config data/config/world.yaml --profile dev

# Validate an existing dataset directory
python -m campaignlift_data.validate data/generated/dev
```

---

## Seed Architecture & Determinism Story

Deterministic reproducibility is guaranteed through an hierarchical stage-seed derivation protocol governed by `data/config/world.yaml`.

- **Global Seed:** `20261006` (Changing this seed defines a new dataset release version).
- **Stage Offsets:** Each generator stage receives an isolated pseudorandom stream derived as `stage_seed = global_seed + offset`:

| Stage | Seed Offset | Derived Stage Seed | Purpose |
| :--- | :---: | :---: | :--- |
| `customers` | `+1` | `20261007` | Latent profile mixture and demographic attribute generation |
| `transactions` | `+2` | `20261008` | Historical transaction sequence simulation |
| `prior_exposures` | `+3` | `20261009` | Historical campaign touchpoints and fatigue simulation |
| `treatment_assignment` | `+4` | `20261010` | Randomized 50/50 RCT treatment assignment among eligible cohort |
| `outcome_noise_and_bernoulli` | `+5` | `20261011` | Gaussian latent logit perturbation and factual conversion draw |
| `split` | `+6` | `20261012` | Deterministic train/validation/test cohort partitioning (60/20/20) |

---

## Dataset Release Versioning & Manifests

Every dataset release generates a committed manifest in `data/manifests/`:
- **Naming Convention:** `cl-synth-<profile>-<global_seed>-<git_sha>.json`
- **Release Tracking:** Manifests record exact row counts, empirical treatment rates, file SHA-256 checksums, and cryptographic verification status.
- **Data Purity:** Full generated datasets (`data/generated/`) remain outside version control (gitignored) to maintain repository hygiene.
