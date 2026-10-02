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
    """A feature frame with true_uplift added fails validation (Step 10.2 acceptance criteria)."""
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

