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
