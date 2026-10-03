# Automated Test Evidence & Verification Log

**Step**: 27 — Automated test pass  
**Date**: 2026-10-04  
**Auditor / Owner**: Assaduzzaman  
**Repository Branch**: `main`  
**Execution Environment**: Python 3.11.9, pytest 9.1.1, Node.js v22, Vite 8.3.2  

---

## 1. Executive Summary

| Test Suite / Target | Command Executed | Total | Passed | Failed | Skipped / Gaps | Duration | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Data Engine & Leakage** | `pytest data/tests -v` | 58 | **58** | 0 | 0 | 53.63s | **PASS** |
| **Machine Learning & Uplift** | `pytest ml/tests -v -o pythonpath=". ml/src data/src"` | 75 | **74** | 1 | 0 | 9.32s | **FAIL (1 test)** |
| **FastAPI Backend Services** | `pytest backend/tests -v` | 50 | **50** | 0 | 0 | 5.72s | **PASS** |
| **Frontend Typecheck** | `npm run typecheck` (`tsc --noEmit`) | — | — | 0 | 0 | 5.81s | **PASS** |
| **Frontend Production Build** | `npx vite build` | 33 modules | 33 | 0 | 0 | 0.42s | **PASS** |
| **Frontend Unit Test Runner** | `npm test` | — | — | — | **Gap Recorded** | — | **GAP** |

---

## 2. Data Engine & Leakage Test Suite

- **Target**: `data/tests/` (Steps 06.1–10.7)
- **Command**:
  ```bash
  pytest data/tests -v
  ```
- **Observed Result**:
  - **Passed**: 58
  - **Failed**: 0
  - **Total**: 58
  - **Execution Time**: 53.63s
  - **Exit Code**: 0

### Test Manifest:
```text
data/tests/test_assignment.py::test_exposure_schema_validation PASSED                   [  1%]
data/tests/test_assignment.py::test_ineligible_audit_separated_from_exposure_file PASSED [  3%]
data/tests/test_assignment.py::test_treatment_rate_inside_bounds_on_large_cohort PASSED [  5%]
data/tests/test_assignment.py::test_eligibility_rules_by_objective PASSED              [  6%]
data/tests/test_assignment.py::test_negative_exposure_schema_rejection PASSED          [  8%]
data/tests/test_campaigns.py::test_current_campaign_validates_against_schema PASSED    [ 10%]
data/tests/test_campaigns.py::test_prior_campaign_end_dates_strictly_before_assigned_at PASSED [ 12%]
data/tests/test_campaigns.py::test_prior_campaigns_do_not_contain_current_modeled_campaign PASSED [ 13%]
data/tests/test_campaigns.py::test_negative_campaign_schema_rejection PASSED          [ 15%]
data/tests/test_customers.py::test_customer_generation_determinism PASSED              [ 17%]
data/tests/test_customers.py::test_customer_schema_validation PASSED                  [ 18%]
data/tests/test_customers.py::test_no_forbidden_columns_in_customer_output PASSED     [ 20%]
data/tests/test_customers.py::test_latent_separation_and_bounds PASSED                [ 22%]
data/tests/test_customers.py::test_customer_uniqueness_enums_and_signup_dates PASSED  [ 24%]
data/tests/test_customers.py::test_seed_variation_changes_attributes PASSED           [ 25%]
data/tests/test_exposures.py::test_prior_dates_strictly_before_assigned_at PASSED      [ 27%]
data/tests/test_exposures.py::test_exposure_counts_differ_across_customers PASSED      [ 29%]
data/tests/test_exposures.py::test_negative_uplift_profile_has_higher_mean_exposures PASSED [ 31%]
data/tests/test_exposures.py::test_compute_observed_fatigue_features PASSED            [ 32%]
data/tests/test_exposures.py::test_negative_exposure_date_at_or_after_assignment_fails PASSED [ 34%]
data/tests/test_features.py::test_feature_table_row_count_equals_exposure_count PASSED [ 36%]
data/tests/test_features.py::test_forbidden_column_intersection_is_empty PASSED        [ 37%]
data/tests/test_features.py::test_transaction_exactly_at_assigned_at_is_excluded PASSED [ 39%]
data/tests/test_features.py::test_negative_feature_schema_rejection_on_forbidden_column PASSED [ 41%]
data/tests/test_outcomes.py::test_outcomes_and_hidden_uplift_schema_conformance PASSED [ 43%]
data/tests/test_outcomes.py::test_hidden_uplift_has_both_positive_and_negative_uplift PASSED [ 44%]
data/tests/test_outcomes.py::test_outcome_consistency_with_y_transacted PASSED         [ 46%]
data/tests/test_outcomes.py::test_no_forbidden_columns_leak_into_outcomes PASSED       [ 48%]
data/tests/test_outcomes.py::test_determinism_two_runs_match PASSED                   [ 50%]
data/tests/test_outcomes.py::test_negative_outcome_schema_rejection PASSED             [ 51%]
data/tests/test_seeds.py::test_load_world_config_success PASSED                       [ 53%]
data/tests/test_seeds.py::test_load_world_config_rejects_missing_global_seed PASSED    [ 55%]
data/tests/test_seeds.py::test_stage_seeds_match_data_plan PASSED                     [ 56%]
data/tests/test_seeds.py::test_stage_offsets_completeness PASSED                      [ 58%]
data/tests/test_seeds.py::test_invalid_stage_name_raises_key_error PASSED             [ 60%]
data/tests/test_splits.py::test_split_shares_within_two_points_on_dev_size PASSED     [ 62%]
data/tests/test_splits.py::test_partition_feature_table_disjoint_and_complete PASSED  [ 63%]
data/tests/test_splits.py::test_split_determinism PASSED                              [ 65%]
data/tests/test_splits.py::test_generate_splits_table_format PASSED                   [ 67%]
data/tests/test_transactions.py::test_transactions_timing_strictly_before_assignment PASSED [ 68%]
data/tests/test_transactions.py::test_transactions_schema_validation PASSED          [ 70%]
data/tests/test_transactions.py::test_high_propensity_produces_higher_mean_count_than_low_propensity PASSED [ 72%]
data/tests/test_transactions.py::test_qr_share_increases_with_qr_affinity PASSED     [ 74%]
data/tests/test_transactions.py::test_merchant_category_rules_on_generated_transactions PASSED [ 75%]
data/tests/test_transactions.py::test_negative_cutoff_detection PASSED                [ 77%]
data/tests/test_transactions.py::test_negative_merchant_category_schema_rejection PASSED [ 79%]
data/tests/test_validate.py::test_fixture_passes_validation PASSED                    [ 81%]
data/tests/test_validate.py::test_mutated_copy_with_duplicate_id_fails PASSED          [ 82%]
data/tests/test_validate.py::test_mutated_copy_with_schema_violation_fails PASSED      [ 84%]
data/tests/test_validate.py::test_mutated_copy_with_orphan_foreign_key_fails PASSED   [ 86%]
data/tests/test_validate.py::test_feature_frame_with_true_uplift_added_fails PASSED   [ 87%]
data/tests/test_validate.py::test_future_event_transaction_at_or_after_assignment_fails PASSED [ 89%]
data/tests/test_validate.py::test_hidden_file_placed_inside_features_directory_fails PASSED [ 91%]
data/tests/test_validate.py::test_zero_negative_uplift_fails_validation PASSED        [ 93%]
data/tests/test_validate.py::test_outcome_inconsistency_fails_validation PASSED        [ 94%]
data/tests/test_validate.py::test_negative_transaction_amount_fails_validation PASSED  [ 96%]
data/tests/test_validate.py::test_null_in_required_field_fails_validation PASSED      [ 98%]
data/tests/test_validate.py::test_extreme_base_rate_generates_warning_without_failing PASSED [100%]
```

---

## 3. Machine Learning & Uplift Modeling Test Suite

- **Target**: `ml/tests/` (Steps 11–16)
- **Command**:
  ```bash
  pytest ml/tests -v -o pythonpath=". ml/src data/src"
  ```
- **Observed Result**:
  - **Passed**: 74
  - **Failed**: 1
  - **Total**: 75
  - **Execution Time**: 9.32s
  - **Exit Code**: 1

### Detailed Breakdown & Failure Analysis:
- **74 Passed Tests**: All baseline models, S-Learners, Logistic T-Learners, LightGBM T-Learners, Qini/AUUC metric calculators, segment reporting slices, oracle evaluations, and model selection rules pass.
- **1 Failed Test**: `ml/tests/test_artifact.py::test_model_binary_is_gitignored`
  - **Failure Output**:
    ```text
    FAILED ml/tests/test_artifact.py::test_model_binary_is_gitignored
    AssertionError: model.joblib is NOT ignored by Git! check-ignore returned:
    assert 1 == 0
    ```
  - **Root Cause & Rationale**:
    In commit `db6bdff` (*synchronize canonical optimized architecture, docker, ci-cd, and team onboarding*), `.gitignore` line 70 was intentionally amended with `!artifacts/models/**/model.joblib` to track the pre-trained winning baseline binary directly in version control. This allows Docker Compose containers and CI/CD pipelines to build and deploy immediately without requiring Kaggle GPU training at startup.
    However, unit test `test_model_binary_is_gitignored` was previously authored in Step 16 under the initial assumption that binaries would never be committed to git.
  - **Integrity Compliance**: Per the Execution Protocol (*"Do not mark a failed suite as passed. Record what actually ran without fabricating numbers"*), this suite is reported as **74 passed, 1 failed**.

---

## 4. Backend Service Test Suite

- **Target**: `backend/tests/` (Steps 17–22)
- **Command**:
  ```bash
  pytest backend/tests -v
  ```
- **Observed Result**:
  - **Passed**: 50
  - **Failed**: 0
  - **Total**: 50
  - **Execution Time**: 5.72s
  - **Exit Code**: 0

### Test Manifest:
```text
backend/tests/test_experiment.py::test_hand_calculation_tiny_table PASSED              [  2%]
backend/tests/test_experiment.py::test_support_rule_nulls_under_minimum_support PASSED [  4%]
backend/tests/test_experiment.py::test_support_rule_computes_sufficient_slice PASSED  [  6%]
backend/tests/test_experiment.py::test_derived_bands_utility PASSED                   [  8%]
backend/tests/test_experiment.py::test_get_experiment_endpoint_on_fixture PASSED      [ 10%]
backend/tests/test_experiment.py::test_get_experiment_with_split_query PASSED        [ 12%]
backend/tests/test_experiment.py::test_get_experiment_campaign_not_found PASSED      [ 14%]
backend/tests/test_experiment.py::test_both_arms_required PASSED                      [ 16%]
backend/tests/test_experiment.py::test_causal_leakage_forbidden_columns_refused PASSED [ 18%]
backend/tests/test_explain.py::test_reason_code_deterministic_rules PASSED             [ 20%]
backend/tests/test_explain.py::test_acceptance_fixture_customer_likely_without_offer PASSED [ 22%]
backend/tests/test_explain.py::test_all_reason_codes_represented_on_fixture PASSED     [ 24%]
backend/tests/test_explain.py::test_feature_contributions_grounded_and_no_leakage PASSED [ 26%]
backend/tests/test_explain.py::test_customer_not_found PASSED                         [ 28%]
backend/tests/test_explain.py::test_campaign_not_found PASSED                         [ 30%]
backend/tests/test_explain.py::test_explain_customer_direct_function PASSED          [ 32%]
backend/tests/test_gemini.py::test_validation_context_contains_fixture_uplift_and_not_true_uplift PASSED [ 34%]
backend/tests/test_gemini.py::test_customer_id_extraction_regex PASSED                [ 36%]
backend/tests/test_gemini.py::test_missing_api_key_returns_copilot_disabled PASSED     [ 38%]
backend/tests/test_gemini.py::test_mock_gemini_query_success PASSED                   [ 40%]
backend/tests/test_gemini.py::test_copilot_run_not_found PASSED                       [ 42%]
backend/tests/test_gemini.py::test_copilot_campaign_not_found PASSED                  [ 44%]
backend/tests/test_gemini.py::test_copilot_provider_unavailable PASSED                [ 46%]
backend/tests/test_health.py::test_health_returns_200_ok PASSED                       [ 48%]
backend/tests/test_health.py::test_ready_returns_200_when_dependencies_valid PASSED   [ 50%]
backend/tests/test_health.py::test_ready_returns_503_when_model_path_is_wrong PASSED  [ 52%]
backend/tests/test_health.py::test_ready_returns_503_when_metadata_json_missing PASSED [ 54%]
backend/tests/test_health.py::test_ready_returns_503_when_model_binary_missing PASSED  [ 56%]
backend/tests/test_health.py::test_ready_returns_503_when_feature_table_missing PASSED [ 58%]
backend/tests/test_health.py::test_ready_returns_503_when_database_not_writable PASSED [ 60%]
backend/tests/test_health.py::test_settings_environment_variable_override PASSED      [ 62%]
backend/tests/test_health.py::test_db_session_and_writability PASSED                  [ 64%]
backend/tests/test_inference.py::test_create_campaign_success PASSED                  [ 66%]
backend/tests/test_inference.py::test_create_campaign_rejects_customer_upload PASSED  [ 68%]
backend/tests/test_inference.py::test_create_campaign_validation_failure PASSED      [ 70%]
backend/tests/test_inference.py::test_get_campaign_by_id PASSED                       [ 72%]
backend/tests/test_inference.py::test_score_campaign_fixture_returns_finite_uplift_and_no_forbidden_field PASSED [ 74%]
backend/tests/test_inference.py::test_score_campaign_pagination PASSED                [ 76%]
backend/tests/test_inference.py::test_score_campaign_rejects_customer_upload_body PASSED [ 78%]
backend/tests/test_inference.py::test_score_campaign_not_found PASSED                 [ 80%]
backend/tests/test_inference.py::test_score_campaign_refuses_feature_mismatch PASSED  [ 82%]
backend/tests/test_inference.py::test_score_campaign_fails_when_model_missing PASSED  [ 84%]
backend/tests/test_optimizer.py::test_budget_never_exceeded_on_fixture PASSED          [ 86%]
backend/tests/test_optimizer.py::test_negative_uplift_excluded_when_asked PASSED      [ 88%]
backend/tests/test_optimizer.py::test_response_strategy_can_include_customer_uplift_rejects PASSED [ 90%]
backend/tests/test_optimizer.py::test_stable_ids_reproducible PASSED                  [ 92%]
backend/tests/test_optimizer.py::test_budget_smaller_than_unit_cost_selects_nobody PASSED [ 94%]
backend/tests/test_optimizer.py::test_invalid_budget_rejected PASSED                  [ 96%]
backend/tests/test_optimizer.py::test_value_per_transaction_ranking PASSED            [ 98%]
backend/tests/test_optimizer.py::test_get_strategy_comparison_endpoint PASSED         [100%]
```

---

## 5. Frontend Quality Gate & Build Verification

### TypeScript Typecheck
- **Command**:
  ```bash
  npm run typecheck  # (tsc --noEmit)
  ```
- **Observed Result**:
  - Exit code: 0
  - Duration: 5.81s
  - 0 type errors across all React 19 / TypeScript 5.7 modules.

### Production Bundle Build
- **Command**:
  ```bash
  npx vite build
  ```
- **Observed Output**:
  ```text
  vite v8.3.2 building client environment for production...
  transforming...
  ✓ 33 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   1.94 kB │ gzip:  0.68 kB
  dist/assets/index-D-J0RCPj.css   36.28 kB │ gzip:  7.50 kB
  dist/assets/index-rGMtKyv7.js   336.20 kB │ gzip: 93.78 kB
  ✓ built in 416ms
  ```
- **Observed Result**:
  - Exit code: 0
  - Built cleanly in 416ms.

### Automated Test Runner Gap
- **Requirement**: *"Run the frontend test or build. If a test runner was never added, record that gap."*
- **Observed Status**: **GAP RECORDED**
- **Details**: `frontend/package.json` contains scripts for `dev`, `build`, `preview`, `format`, `typecheck`, and `lint`, but does not configure an automated client test runner (such as `vitest` or `jest`). UI correctness relies on TypeScript compile-time checking (`tsc --noEmit`), linter validation, and end-to-end integration with the FastAPI backend.
