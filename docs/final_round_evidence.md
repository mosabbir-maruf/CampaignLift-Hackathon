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
| Frozen-test AUUC point estimate and bootstrap interval | MEASURED | Point: 0.4841 (Historical: 0.1755), 95% CI: [-0.1557, 0.9377] | python -m campaignlift_ml.bootstrap -> docs/bootstrap_intervals.json |
| Frozen-test Qini point estimate and bootstrap interval | MEASURED | Point: 1.0438 (Historical: 65.2257), 95% CI: [-0.1060, 2.2788] | python -m campaignlift_ml.bootstrap -> docs/bootstrap_intervals.json |
| Repeated-seed AUUC spread | TO BE MEASURED | | |
| Assignment-sensitivity comparison | TO BE MEASURED | | |
| Ablation ladder: random, response, uplift, uplift_plus_budget | TO BE MEASURED | | |
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
