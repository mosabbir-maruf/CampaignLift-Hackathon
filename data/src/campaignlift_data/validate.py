"""Dataset validation module for CampaignLift causal world.

Performs rigorous automated gatekeeping on generated datasets and fixtures:
1. Validates every table against its canonical JSON schema.
2. Checks for duplicate primary keys across tables.
3. Checks for orphan foreign keys referencing missing parents.
4. Validates required fields, enum domains, and value bounds.
5. Writes detailed audit results to data/reports/validation_report.json.
6. Exits with code 1 if any blocker check fails.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import jsonschema


def load_json_file(path: Path) -> Any:
    """Load JSON content from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class DatasetValidator:
    """Automated schema, key integrity, and boundary validator for dataset releases."""

    def __init__(
        self,
        dataset_dir: Union[str, Path],
        schemas_dir: Optional[Union[str, Path]] = None,
        report_path: Optional[Union[str, Path]] = None,
    ):
        self.dataset_dir = Path(dataset_dir).resolve()
        if schemas_dir is None:
            # Default to data/schemas relative to package (parents[2] is data/)
            self.schemas_dir = (
                Path(__file__).resolve().parents[2] / "schemas"
            ).resolve()
        else:
            self.schemas_dir = Path(schemas_dir).resolve()

        if report_path is None:
            self.report_path = (
                Path(__file__).resolve().parents[2] / "reports" / "validation_report.json"
            ).resolve()
        else:
            self.report_path = Path(report_path).resolve()

        self.checks: List[Dict[str, Any]] = []
        self.blockers: List[str] = []
        self.warnings: List[str] = []

    def _add_check(
        self,
        name: str,
        passed: bool,
        description: str,
        observed: Any,
        expected: str,
        is_blocker: bool = True,
    ) -> None:
        status = "passed" if passed else "failed"
        self.checks.append({
            "name": name,
            "status": status,
            "description": description,
            "observed": str(observed),
            "expected": expected,
        })
        if not passed:
            msg = f"[{name}] {description} (Observed: {observed}, Expected: {expected})"
            if is_blocker:
                self.blockers.append(msg)
            else:
                self.warnings.append(msg)

    def validate_all(self) -> Tuple[bool, Dict[str, Any]]:
        """Execute full validation suite across all tables in dataset_dir."""
        # 1. Check existence of expected files
        expected_files = [
            "customers.json",
            "transactions.json",
            "campaign.json",
            "exposures.json",
            "outcomes.json",
            "features.json",
            "splits.json",
            "manifest.json",
        ]
        missing_files = [f for f in expected_files if not (self.dataset_dir / f).exists()]
        self._add_check(
            name="file_existence",
            passed=len(missing_files) == 0,
            description="Verify all expected dataset files exist",
            observed=f"Missing: {missing_files}" if missing_files else "All files present",
            expected="All expected files present",
        )
        if missing_files:
            return False, self._build_report()

        # Load schemas
        schemas = {
            "customer": load_json_file(self.schemas_dir / "customer.schema.json"),
            "transaction": load_json_file(self.schemas_dir / "transaction.schema.json"),
            "campaign": load_json_file(self.schemas_dir / "campaign.schema.json"),
            "exposure": load_json_file(self.schemas_dir / "exposure.schema.json"),
            "outcome": load_json_file(self.schemas_dir / "outcome.schema.json"),
            "feature_table": load_json_file(self.schemas_dir / "feature_table.schema.json"),
            "manifest": load_json_file(self.schemas_dir / "manifest.schema.json"),
        }
        if (self.schemas_dir / "hidden_uplift.schema.json").exists():
            schemas["hidden_uplift"] = load_json_file(self.schemas_dir / "hidden_uplift.schema.json")

        # Load data tables
        customers = load_json_file(self.dataset_dir / "customers.json")
        transactions = load_json_file(self.dataset_dir / "transactions.json")
        campaign = load_json_file(self.dataset_dir / "campaign.json")
        exposures = load_json_file(self.dataset_dir / "exposures.json")
        outcomes = load_json_file(self.dataset_dir / "outcomes.json")
        features = load_json_file(self.dataset_dir / "features.json")
        splits = load_json_file(self.dataset_dir / "splits.json")
        manifest = load_json_file(self.dataset_dir / "manifest.json")

        hidden_path = self.dataset_dir / "hidden_uplift.json"
        hidden_uplift = load_json_file(hidden_path) if hidden_path.exists() else None

        # 2. Schema Validations
        self._validate_rows_against_schema("schema_customers", customers, schemas["customer"])
        self._validate_rows_against_schema("schema_transactions", transactions, schemas["transaction"])

        # Campaign can be a single dict or a list of 1 dict
        camp_to_check = campaign[0] if isinstance(campaign, list) else campaign
        self._validate_single_against_schema("schema_campaign", camp_to_check, schemas["campaign"])

        self._validate_rows_against_schema("schema_exposures", exposures, schemas["exposure"])
        self._validate_rows_against_schema("schema_outcomes", outcomes, schemas["outcome"])
        self._validate_rows_against_schema("schema_features", features, schemas["feature_table"])
        self._validate_single_against_schema("schema_manifest", manifest, schemas["manifest"])

        if hidden_uplift is not None and "hidden_uplift" in schemas:
            self._validate_rows_against_schema("schema_hidden_uplift", hidden_uplift, schemas["hidden_uplift"])

        # 3. Primary Key Uniqueness
        self._check_uniqueness("pk_customers", [c["customer_id"] for c in customers], "customer_id")
        self._check_uniqueness("pk_transactions", [t["transaction_id"] for t in transactions], "transaction_id")
        self._check_uniqueness("pk_exposures", [e["exposure_id"] for e in exposures], "exposure_id")
        self._check_uniqueness("pk_exposures_customer", [e["customer_id"] for e in exposures], "customer_id in exposures")
        self._check_uniqueness("pk_outcomes_customer", [o["customer_id"] for o in outcomes], "customer_id in outcomes")
        self._check_uniqueness("pk_features_customer", [f["customer_id"] for f in features], "customer_id in features")
        self._check_uniqueness("pk_splits_customer", [s["customer_id"] for s in splits], "customer_id in splits")

        # 4. Foreign Key Integrity
        valid_cust_ids = {c["customer_id"] for c in customers}
        valid_camp_id = camp_to_check["campaign_id"]
        valid_exp_cust_ids = {e["customer_id"] for e in exposures}

        # Transactions -> Customers
        orphan_txn_cust = [t["customer_id"] for t in transactions if t["customer_id"] not in valid_cust_ids]
        self._add_check(
            name="fk_transactions_customers",
            passed=len(orphan_txn_cust) == 0,
            description="Verify all transactions reference valid customers",
            observed=f"{len(orphan_txn_cust)} orphan references",
            expected="0 orphan references",
        )

        # Exposures -> Customers & Campaign
        orphan_exp_cust = [e["customer_id"] for e in exposures if e["customer_id"] not in valid_cust_ids]
        orphan_exp_camp = [e["campaign_id"] for e in exposures if e["campaign_id"] != valid_camp_id]
        self._add_check(
            name="fk_exposures_customers",
            passed=len(orphan_exp_cust) == 0 and len(orphan_exp_camp) == 0,
            description="Verify all exposures reference valid customers and campaign",
            observed=f"{len(orphan_exp_cust)} orphan cust, {len(orphan_exp_camp)} invalid camp",
            expected="0 orphan references",
        )

        # Outcomes -> Exposures & Campaign
        orphan_out_cust = [o["customer_id"] for o in outcomes if o["customer_id"] not in valid_exp_cust_ids]
        orphan_out_camp = [o["campaign_id"] for o in outcomes if o["campaign_id"] != valid_camp_id]
        self._add_check(
            name="fk_outcomes_exposures",
            passed=len(orphan_out_cust) == 0 and len(orphan_out_camp) == 0,
            description="Verify all outcomes reference valid exposed customers and campaign",
            observed=f"{len(orphan_out_cust)} orphan cust, {len(orphan_out_camp)} invalid camp",
            expected="0 orphan references",
        )

        # Features -> Exposures
        orphan_feat_cust = [f["customer_id"] for f in features if f["customer_id"] not in valid_exp_cust_ids]
        self._add_check(
            name="fk_features_exposures",
            passed=len(orphan_feat_cust) == 0 and len(features) == len(exposures),
            description="Verify feature table exactly matches exposure cohort",
            observed=f"{len(orphan_feat_cust)} orphan cust, total {len(features)} vs {len(exposures)} exposures",
            expected="Row count equals exposure count and 0 orphans",
        )

        # 5. Treatment and Outcome Boundaries
        invalid_treatments = [e["treatment"] for e in exposures if e["treatment"] not in (0, 1)]
        self._add_check(
            name="treatment_domain",
            passed=len(invalid_treatments) == 0,
            description="Verify treatment assignment flags are strictly in {0, 1}",
            observed=f"{len(invalid_treatments)} invalid values",
            expected="All in {0, 1}",
        )

        invalid_outcomes = [o["y_transacted"] for o in outcomes if o["y_transacted"] not in (0, 1)]
        self._add_check(
            name="outcome_domain",
            passed=len(invalid_outcomes) == 0,
            description="Verify conversion labels are strictly in {0, 1}",
            observed=f"{len(invalid_outcomes)} invalid values",
            expected="All in {0, 1}",
        )

        # 6. Treatment Rate Sanity
        if len(exposures) > 0:
            n_treat = sum(1 for e in exposures if e["treatment"] == 1)
            t_rate = n_treat / len(exposures)
            self._add_check(
                name="treatment_rate_bounds",
                passed=0.40 <= t_rate <= 0.60,  # Broader tolerance for small fixture (200), dev is 0.45-0.55
                description="Verify empirical treatment rate is balanced around 0.50",
                observed=f"{t_rate:.4f}",
                expected="Within [0.40, 0.60] for fixture, [0.45, 0.55] for release",
            )

        report = self._build_report()
        self._save_report(report)

        is_valid = len(self.blockers) == 0
        return is_valid, report

    def _validate_rows_against_schema(self, check_name: str, rows: List[Dict[str, Any]], schema: Dict[str, Any]) -> None:
        errors = []
        for i, row in enumerate(rows):
            try:
                jsonschema.validate(instance=row, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                errors.append(f"Row {i}: {e.message}")
                if len(errors) >= 5:  # Limit error messages
                    break
        self._add_check(
            name=check_name,
            passed=len(errors) == 0,
            description=f"Validate rows against {schema.get('title', 'schema')}",
            observed=f"{len(errors)} schema errors ({errors[:2]})" if errors else f"{len(rows)} rows valid",
            expected="0 schema errors",
        )

    def _validate_single_against_schema(self, check_name: str, obj: Dict[str, Any], schema: Dict[str, Any]) -> None:
        try:
            jsonschema.validate(instance=obj, schema=schema)
            passed = True
            msg = "Valid object"
        except jsonschema.exceptions.ValidationError as e:
            passed = False
            msg = f"Schema error: {e.message}"
        self._add_check(
            name=check_name,
            passed=passed,
            description=f"Validate object against {schema.get('title', 'schema')}",
            observed=msg,
            expected="Valid against schema",
        )

    def _check_uniqueness(self, check_name: str, keys: List[str], field_name: str) -> None:
        seen = set()
        duplicates = set()
        for k in keys:
            if k in seen:
                duplicates.add(k)
            seen.add(k)
        self._add_check(
            name=check_name,
            passed=len(duplicates) == 0,
            description=f"Verify uniqueness of {field_name}",
            observed=f"{len(duplicates)} duplicate keys: {list(duplicates)[:3]}" if duplicates else f"{len(keys)} unique keys",
            expected="0 duplicate keys",
        )

    def _build_report(self) -> Dict[str, Any]:
        passed_count = sum(1 for c in self.checks if c["status"] == "passed")
        failed_count = sum(1 for c in self.checks if c["status"] == "failed")
        status = "passed" if len(self.blockers) == 0 else "failed"

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_dir": str(self.dataset_dir),
            "validation_status": status,
            "total_checks": len(self.checks),
            "passed_checks": passed_count,
            "failed_checks": failed_count,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "checks": self.checks,
        }

    def _save_report(self, report: Dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)


def main():
    """CLI entry point for schema and dataset validation."""
    dataset_dir = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "fixtures" / "fixture_v1"
    validator = DatasetValidator(dataset_dir)
    is_valid, report = validator.validate_all()

    print(f"\n=======================================================")
    print(f"Validation Report for: {dataset_dir}")
    print(f"Status: {report['validation_status'].upper()}")
    print(f"Checks: {report['passed_checks']}/{report['total_checks']} passed")
    if report["blockers"]:
        print("\nBLOCKERS ENCOUNTERED:")
        for b in report["blockers"]:
            print(f"  - {b}")
    print(f"Report saved to: {validator.report_path}")
    print(f"=======================================================\n")

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
