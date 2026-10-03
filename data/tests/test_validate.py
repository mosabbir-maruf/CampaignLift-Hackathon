"""Tests for dataset validator module."""

import json
from pathlib import Path
import shutil
import sys
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.validate import DatasetValidator


def test_fixture_passes_validation():
    """Canonical test fixture in data/fixtures/fixture_v1 passes all validation checks."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    report_file = Path(__file__).resolve().parents[1] / "reports" / "validation_report.json"

    validator = DatasetValidator(dataset_dir=fixture_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is True, f"Fixture failed validation: {report['blockers']}"
    assert report["validation_status"] == "passed"
    assert report["failed_checks"] == 0
    assert report_file.exists()


def test_mutated_copy_with_duplicate_id_fails(tmp_path):
    """A mutated copy of the dataset containing a duplicate ID fails validation (acceptance criteria)."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_fixture"
    shutil.copytree(fixture_dir, mutated_dir)

    # Inject duplicate customer_id in customers.json
    customers_file = mutated_dir / "customers.json"
    with open(customers_file, "r", encoding="utf-8") as f:
        customers = json.load(f)

    assert len(customers) > 1
    # Duplicate the first customer record
    duplicated_customer = dict(customers[0])
    customers.append(duplicated_customer)

    with open(customers_file, "w", encoding="utf-8") as f:
        json.dump(customers, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    # Must fail
    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("pk_customers" in b for b in report["blockers"])


def test_mutated_copy_with_schema_violation_fails(tmp_path):
    """A mutated copy with invalid enum or schema violation fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_schema"
    shutil.copytree(fixture_dir, mutated_dir)

    # Invalidate age_band in customers.json
    customers_file = mutated_dir / "customers.json"
    with open(customers_file, "r", encoding="utf-8") as f:
        customers = json.load(f)

    customers[0]["age_band"] = "invalid_age_band"
    with open(customers_file, "w", encoding="utf-8") as f:
        json.dump(customers, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("schema_customers" in b for b in report["blockers"])


def test_mutated_copy_with_orphan_foreign_key_fails(tmp_path):
    """A mutated copy with an orphan foreign key reference fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_fk"
    shutil.copytree(fixture_dir, mutated_dir)

    # Invalidate customer_id in transactions.json to non-existent customer
    txns_file = mutated_dir / "transactions.json"
    with open(txns_file, "r", encoding="utf-8") as f:
        txns = json.load(f)

    txns[0]["customer_id"] = "C99999999"
    with open(txns_file, "w", encoding="utf-8") as f:
        json.dump(txns, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("fk_transactions_customers" in b for b in report["blockers"])


def test_feature_frame_with_true_uplift_added_fails(tmp_path):
    """A feature frame with true_uplift added fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_features"
    shutil.copytree(fixture_dir, mutated_dir)

    features_file = mutated_dir / "features.json"
    with open(features_file, "r", encoding="utf-8") as f:
        features = json.load(f)

    # Inject forbidden column 'true_uplift' into the first feature record
    assert len(features) > 0
    features[0]["true_uplift"] = 0.045

    with open(features_file, "w", encoding="utf-8") as f:
        json.dump(features, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("leakage_forbidden_columns" in b for b in report["blockers"])


def test_future_event_transaction_at_or_after_assignment_fails(tmp_path):
    """A transaction occurring at or after assignment time fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_future_event"
    shutil.copytree(fixture_dir, mutated_dir)

    features_file = mutated_dir / "features.json"
    with open(features_file, "r", encoding="utf-8") as f:
        features = json.load(f)
    assert len(features) > 0
    target_cid = features[0]["customer_id"]

    txns_file = mutated_dir / "transactions.json"
    with open(txns_file, "r", encoding="utf-8") as f:
        txns = json.load(f)

    # Find a transaction for target_cid and set event_time on or after campaign start (2024-02-01)
    modified = False
    for t in txns:
        if t["customer_id"] == target_cid:
            t["event_time"] = "2024-02-05T12:00:00Z"
            modified = True
            break
    assert modified, f"Customer {target_cid} should have transactions"

    with open(txns_file, "w", encoding="utf-8") as f:
        json.dump(txns, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("leakage_future_events" in b for b in report["blockers"])



def test_hidden_file_placed_inside_features_directory_fails(tmp_path):
    """A hidden oracle file placed inside the features directory fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_hidden_placement"
    shutil.copytree(fixture_dir, mutated_dir)

    features_dir = mutated_dir / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    leaked_hidden_file = features_dir / "hidden_potential_outcomes.json"
    leaked_hidden_file.write_text('{"note": "leaked"}', encoding="utf-8")

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("leakage_hidden_file_placement" in b for b in report["blockers"])


def test_zero_negative_uplift_fails_validation(tmp_path):
    """Hidden oracle with zero negative uplift fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_no_neg_uplift"
    shutil.copytree(fixture_dir, mutated_dir)

    hidden_file = mutated_dir / "hidden_uplift.json"
    with open(hidden_file, "r", encoding="utf-8") as f:
        uplift_rows = json.load(f)

    # Force all true_uplift values to be strictly positive
    for row in uplift_rows:
        row["true_uplift"] = abs(row["true_uplift"]) + 0.05

    with open(hidden_file, "w", encoding="utf-8") as f:
        json.dump(uplift_rows, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    # Must fail because zero negative-uplift customers violate release blocker
    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("uplift_negative_contrast" in b for b in report["blockers"])


def test_outcome_inconsistency_fails_validation(tmp_path):
    """Inconsistent outcome rows (e.g. y=0 with nonzero amount) fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_outcome_inconsistency"
    shutil.copytree(fixture_dir, mutated_dir)

    outcomes_file = mutated_dir / "outcomes.json"
    with open(outcomes_file, "r", encoding="utf-8") as f:
        outcomes = json.load(f)

    # Invalidate first row: y=0 but nonzero spend and transaction count
    outcomes[0]["y_transacted"] = 0
    outcomes[0]["txn_count_window"] = 2
    outcomes[0]["txn_amount_window_bdt"] = 250.0

    with open(outcomes_file, "w", encoding="utf-8") as f:
        json.dump(outcomes, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("outcome_consistency" in b for b in report["blockers"])


def test_negative_transaction_amount_fails_validation(tmp_path):
    """A real transaction with amount <= 0 fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_txn_amount"
    shutil.copytree(fixture_dir, mutated_dir)

    txns_file = mutated_dir / "transactions.json"
    with open(txns_file, "r", encoding="utf-8") as f:
        txns = json.load(f)

    txns[0]["amount_bdt"] = -5.0

    with open(txns_file, "w", encoding="utf-8") as f:
        json.dump(txns, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("transaction_amount_positive" in b for b in report["blockers"])


def test_null_in_required_field_fails_validation(tmp_path):
    """Null in a required field fails validation."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_null_field"
    shutil.copytree(fixture_dir, mutated_dir)

    cust_file = mutated_dir / "customers.json"
    with open(cust_file, "r", encoding="utf-8") as f:
        custs = json.load(f)

    custs[0]["region_code"] = None

    with open(cust_file, "w", encoding="utf-8") as f:
        json.dump(custs, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    assert is_valid is False
    assert report["validation_status"] == "failed"
    assert any("null_checks_required" in b or "schema_customers" in b for b in report["blockers"])


def test_extreme_base_rate_generates_warning_without_failing(tmp_path):
    """Extreme base rate produces a warning in the report but does not fail the run."""
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "fixture_v1"
    mutated_dir = tmp_path / "mutated_extreme_base_rate"
    shutil.copytree(fixture_dir, mutated_dir)

    outcomes_file = mutated_dir / "outcomes.json"
    with open(outcomes_file, "r", encoding="utf-8") as f:
        outcomes = json.load(f)

    # Set all rows to y=1 so base rate is 100% (> 80% warning threshold)
    for o in outcomes:
        o["y_transacted"] = 1
        o["txn_count_window"] = 1
        o["txn_amount_window_bdt"] = 50.0

    with open(outcomes_file, "w", encoding="utf-8") as f:
        json.dump(outcomes, f)

    report_file = tmp_path / "report.json"
    validator = DatasetValidator(dataset_dir=mutated_dir, report_path=report_file)
    is_valid, report = validator.validate_all()

    # Warning must NOT flip exit code or status to failed
    assert is_valid is True
    assert report["validation_status"] == "passed"
    assert any("warning_outcome_base_rate" in w for w in report["warnings"])


