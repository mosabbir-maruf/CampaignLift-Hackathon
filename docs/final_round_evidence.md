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
| Ablation ladder: random, response, uplift, uplift_plus_budget | MEASURED (fixture) | 4 rungs evaluated under shared 500 BDT budget on 103 eligible fixture customers | pytest backend/tests/test_optimizer.py |
| Incremental transactions | MEASURED (fixture) | uplift: +6.0, response: +4.166, random: -6.0 (fixture-only; formula: measured_incremental_rate * selected_count under sufficient support) | pytest backend/tests/test_optimizer.py |
| Cost per incremental transaction | MEASURED (fixture) | uplift: 83.33 BDT, response: 120.02 BDT, random: N/A (spend / expected_incremental_transactions; null if support insufficient) | pytest backend/tests/test_optimizer.py |
| Net campaign result | MEASURED (fixture) | Null when transaction value missing (NOT_PROVIDED); +100.00 BDT for uplift when assumed value = 100.0 BDT (ASSUMED, fixture-only: (expected_inc_txns * value) - spend) | pytest backend/tests/test_optimizer.py |
| Fatigue or negative-uplift share | MEASURED (fixture) | Fatigue: 0.0% uplift / 0.0% response (band 3+ on prior 30d); Negative uplift: 0.0% uplift, 15.0% response, 30.0% random | pytest backend/tests/test_optimizer.py |
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


## Synthetic Experiment Business Scorecard (FE-09)

> **Evidence Boundary:** Synthetic randomized experiment; not a controlled commercial holdout.
> Evaluated strictly on the synthetic population (`data/fixtures/fixture_v1`) across the four targeting strategies under shared constraints. These figures represent synthetic experimental fixture evidence and do NOT reflect real bKash MFS commercial holdouts, production ROI, or commercial campaign profitability.

### Metric Definitions and Boundaries

1. **Expected Incremental Transactions (`expected_incremental_transactions`):**
   - **Formula:** `measured_incremental_rate * selected_count`
   - **Support Rule:** Calculated only when the strategy has sufficient randomized measurement support (`>= 5` in treated and control arms) and `measured_incremental_rate` is available; otherwise strictly `null`.
   - **Boundary:** Never substitutes model probability, uplift prediction, ATE, or heuristic assumptions.
   - **Fixture Evidence:** Uplift targets 20 customers with `+0.3000` measured incremental rate $\rightarrow$ `+6.0` expected incremental transactions.

2. **Cost per Incremental Transaction (`cost_per_incremental_transaction_bdt`):**
   - **Formula:** `spend_bdt / expected_incremental_transactions`
   - **Support Rule:** Preserves FE-08 calculation; requires sufficient support and `incremental_rate > 0`. Returns `null` when support is insufficient or incremental rate is non-positive.
   - **Fixture Evidence:** Uplift: `83.33 BDT` ($500 / 6.0$); Response: `120.02 BDT` ($500 / 4.166$).

3. **Net Campaign Result (`net_result` & `value_assumption`):**
   - **Formula:** `(expected_incremental_transactions * value_per_incremental_transaction_bdt) - spend`
   - **Manager Input:** `value_per_incremental_transaction_bdt` must be explicitly provided and strictly positive (`> 0`). There is **no default commercial transaction value**.
   - **Assumption Flag:**
     - When explicitly supplied (`> 0`): `value_assumption = "ASSUMED"`, and `net_result` is computed if expected incremental transactions are available (otherwise `null`).
     - When not supplied: `net_result = null` and `value_assumption = "NOT_PROVIDED"`.
     - Zero or negative values are strictly rejected (HTTP 400 validation error).
   - **Boundary:** ROI, savings, or commercial profit are never displayed or implied when transaction value has not been explicitly supplied.

4. **Fatigue Rate (`fatigue_rate`):**
   - **Formula:** `selected_customers_in_highest_prior_exposure_band / selected_count`
   - **Bands:** Canonical responsible AI exposure bands (`"0"`, `"1-2"`, `"3+"`). Highest band is `"3+"`.
   - **Boundary:** Uses existing prior exposure features (`prior_exposure_band`, `exposure_band`, `campaign_exposures_prior_30d`, `campaign_exposures_prior_90d`). If prior exposure information is unavailable, returns `null`. No fatigue model or arbitrary thresholds are invented.

5. **Cannibalization / Negative Uplift Share (`negative_uplift_share`):**
   - **Formula:** `selected_customers_with_negative_uplift / selected_count`
   - **Boundary:** Reuses predicted causal uplift scores from the candidate population. If uplift information is unavailable, returns `null`. Preserves measured empirical rate without fabricating causal estimators.

### Complete Strategy Scorecard Table (Fixture Evidence)

| Strategy | Selected Count | Spend (BDT) | Support | Measured Incr. Rate | Expected Incr. Txns | Cost / Incr. Txn (BDT) | Net Result (No Value Input) | Net Result (Assumed @ 100 BDT) | Fatigue Rate (Band 3+) | Negative Uplift Share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `random` | 20 | 500.0 | sufficient | -0.3000 | -6.0 | N/A | null (`NOT_PROVIDED`) | -1,100.00 BDT (`ASSUMED`) | 0.0% | 30.0% |
| `response` | 20 | 500.0 | sufficient | +0.2083 | +4.166 | 120.02 | null (`NOT_PROVIDED`) | -83.40 BDT (`ASSUMED`) | 0.0% | 15.0% |
| `uplift` | 20 | 500.0 | sufficient | +0.3000 | +6.0 | 83.33 | null (`NOT_PROVIDED`) | +100.00 BDT (`ASSUMED`) | 0.0% | 0.0% |
| `uplift_plus_budget` | 20 | 500.0 | sufficient | +0.3000 | +6.0 | 83.33 | null (`NOT_PROVIDED`) | +100.00 BDT (`ASSUMED`) | 0.0% | 0.0% |


