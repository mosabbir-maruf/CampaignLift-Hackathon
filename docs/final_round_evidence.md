# Final Round Evidence Ledger

The population is synthetic.
The experiment is a randomized treatment/control split inside that synthetic world.
The experiment is not a controlled commercial holdout.

## Evidence Policy

Judge-facing docs may quote a numeral only when this file has a measured value and the command that produced it.

## Baseline Identifiers

- Frozen Model: `cl-model-ml_dev_20261006-lgbm_s_learner-r01`
- Dataset Version: `cl-synth-ml_dev-20261006-8ad556a`

## Metric Ledger

| Metric | Status | Value | Command / Evidence Source |
| --- | --- | --- | --- |
| Frozen-test AUUC point estimate and bootstrap interval | TO BE MEASURED | | |
| Frozen-test Qini point estimate and bootstrap interval | TO BE MEASURED | | |
| Repeated-seed AUUC spread | TO BE MEASURED | | |
| Assignment-sensitivity comparison | TO BE MEASURED | | |
| Ablation ladder: random, response, uplift, uplift_plus_budget | MEASURED (fixture) | 4 rungs evaluated under shared 500 BDT budget on 103 eligible fixture customers | pytest backend/tests/test_optimizer.py |
| Incremental transactions | TO BE MEASURED | | |
| Cost per incremental transaction | TO BE MEASURED | | |
| Net campaign result | TO BE MEASURED | | |
| Fatigue or negative-uplift share | TO BE MEASURED | | |
| Fairness run id and population size | MEASURED | run_fairness_slice_fixture_v1, 23 validation rows (fixture_v1) | python -m ml.src.campaignlift_ml.report -> docs/fairness_slice_evaluation.json |
| Score latency p50, p95, p99 | TO BE MEASURED | | |
| Concurrent campaign scoring result | TO BE MEASURED | | |
| Restart persistence result | TO BE MEASURED | | |
| Drift status | TO BE MEASURED | | |
| CORS policy | TO BE MEASURED | | |
| Login roles | TO BE MEASURED | | |

## Ablation Ladder: Four-Rung Strategy Comparison (Fixture)

> **Evaluation Label:** `fixture` (synthetic fixture evaluation; not a commercial outcome).
> **Shared Evaluation Constraints:**
> - Shared Population: 103 eligible customers (`data/fixtures/fixture_v1/features.json`)
> - Shared Budget: 500.0 BDT
> - Shared Offer Cost: 25.0 BDT per targeted customer

### Strategy Definitions

1. `random`: Uniformly random selection among eligible customers under the budget constraint.
2. `response`: Ranks by predicted response probability ($P(Y=1 \mid T=1)$, `p_treat`) descending under the budget constraint (propensity model baseline; does not filter negative uplift).
3. `uplift`: Ranks strictly by predicted causal uplift ($P(Y=1 \mid T=1) - P(Y=1 \mid T=0)$) descending under the budget constraint.
4. `uplift_plus_budget`: Causal uplift with budget optimizer. When `value_per_incremental_transaction_bdt` is supplied, ranks by net value $((uplift \times \text{assumed\_value}) - \text{unit\_cost})$ dropping negative net value, then greedy under budget. When value is not supplied, ranks by predicted uplift and stops when marginal predicted uplift is below zero, greedy under the same budget constraint.

### Fixture Measurement Table

| Strategy | Selected Count | Spend (BDT) | Expected Incr. Value | Test Support | Measured Incr. Response | Cost per Incr. Txn (BDT) | Negative Uplift Share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `random` | 20 | 500.0 | 0.1789 | sufficient | -0.3000 | N/A | 30.0% |
| `response` | 20 | 500.0 | 1.0551 | sufficient | +0.2083 | 120.02 | 15.0% |
| `uplift` | 20 | 500.0 | 1.5389 | sufficient | +0.3000 | 83.33 | 0.0% |
| `uplift_plus_budget` | 20 | 500.0 | 1.5389 | sufficient | +0.3000 | 83.33 | 0.0% |

