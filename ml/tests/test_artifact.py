"""Tests for Model Artifact Packaging and Fresh-Process Verification (Step 16).

Verifies:
1. All JSON metadata files exist in artifacts/models/<model_version>/.
2. Model binary model.joblib exists and is gitignored.
3. In-process loading and scoring on the test fixture.
4. Fresh subprocess loading and smoke score verification matching metadata within floating-point tolerance.
"""

import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "models" / "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
FIXTURE_PATH = REPO_ROOT / "data" / "fixtures" / "fixture_v1" / "features.json"


def test_artifact_files_exist():
    """Verify that all required artifact files exist on disk."""
    assert ARTIFACT_DIR.is_dir(), f"Artifact directory not found at {ARTIFACT_DIR}"

    required_files = [
        "metadata.json",
        "feature_list.json",
        "validation_metrics.json",
        "test_metrics.json",
        "model.joblib",
    ]
    for fname in required_files:
        p = ARTIFACT_DIR / fname
        assert p.is_file(), f"Required artifact file missing: {fname}"
        assert p.stat().st_size > 0, f"Artifact file is empty: {fname}"


def test_model_binary_is_gitignored():
    """Verify model.joblib is ignored by Git and will never be committed."""
    joblib_path = ARTIFACT_DIR / "model.joblib"
    assert joblib_path.is_file()

    # Query Git check-ignore
    res = subprocess.run(
        ["git", "check-ignore", str(joblib_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"model.joblib is NOT ignored by Git! check-ignore returned: {res.stdout}"


def test_metadata_fields():
    """Verify all metadata fields defined in kaggle_plan.md are present."""
    metadata_path = ARTIFACT_DIR / "metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_version"] == "cl-model-ml_dev_20261006-lgbm_s_learner-r01"
    assert meta["model_family"] == "lightgbm_s_learner"
    assert meta["candidate_id"] == "U2"
    assert meta["dataset_version"] == "cl-synth-ml_dev-20261006-8ad556a"
    assert meta["global_seed"] == 20261006
    assert len(meta["feature_names"]) == 22
    assert "OneHotEncoder" in meta["categorical_encoding"]
    assert "lightgbm" in meta["library_versions"]
    assert "scikit-learn" in meta["library_versions"]
    assert meta["git_sha"] is not None and len(meta["git_sha"]) >= 7
    assert meta["metrics"]["validation"]["validation_qini_score"] > 0
    assert meta["metrics"]["test"]["test_qini_score"] > 0
    assert "Rank candidates by validation Qini" in meta["selection_rule"]
    assert meta["fixture_smoke_score"]["n_fixture_rows"] == 103


def test_in_process_artifact_load_and_score():
    """Verify in-process loading and scoring on the test fixture."""
    from campaignlift_ml.artifact import load_model_artifact

    artifact = load_model_artifact(ARTIFACT_DIR)
    assert artifact.model_version == "cl-model-ml_dev_20261006-lgbm_s_learner-r01"

    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixture_df = pd.DataFrame(json.load(f))

    preds = artifact.predict_uplift(fixture_df)
    assert len(preds.p_treat) == len(fixture_df)
    assert len(preds.p_control) == len(fixture_df)
    assert len(preds.uplift) == len(fixture_df)

    # Sanity bounds
    assert np.all((preds.p_treat >= 0.0) & (preds.p_treat <= 1.0))
    assert np.all((preds.p_control >= 0.0) & (preds.p_control <= 1.0))
    assert np.all((preds.uplift >= -1.0) & (preds.uplift <= 1.0))
    assert np.std(preds.uplift) > 0.001

    scored = artifact.score_cohort(fixture_df)
    assert "customer_id" in scored.columns
    assert "uplift_rank" in scored.columns
    assert scored["uplift_rank"].min() == 1
    assert scored["uplift_rank"].max() == len(fixture_df)


def test_feature_mismatch_raises():
    """Verify that scoring a DataFrame missing required features raises ValueError."""
    from campaignlift_ml.artifact import load_model_artifact

    artifact = load_model_artifact(ARTIFACT_DIR)
    bad_df = pd.DataFrame({"some_random_column": [1, 2, 3]})

    with pytest.raises(ValueError, match="missing .* required feature columns"):
        artifact.predict_uplift(bad_df)


def test_fresh_process_smoke_score_matches_saved_validation():
    """Verify that loading the artifact in a fresh Python process matches saved fixture smoke scores.

    This directly satisfies the Step 16 acceptance criteria:
    'Fresh-process smoke score matches the saved validation routine on the fixture within floating point tolerance.'
    """
    metadata_path = ARTIFACT_DIR / "metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    saved_smoke = meta["fixture_smoke_score"]

    # Script to run in fresh subprocess
    script = f"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(r"{REPO_ROOT}")
sys.path.insert(0, str(REPO_ROOT / "ml" / "src"))

from campaignlift_ml.artifact import load_model_artifact

artifact = load_model_artifact(r"{ARTIFACT_DIR}")

with open(r"{FIXTURE_PATH}", "r", encoding="utf-8") as f:
    fixture_df = pd.DataFrame(json.load(f))

preds = artifact.predict_uplift(fixture_df)

fresh_scores = {{
    "n_fixture_rows": len(fixture_df),
    "mean_p_treat": round(float(np.mean(preds.p_treat)), 6),
    "mean_p_control": round(float(np.mean(preds.p_control)), 6),
    "mean_uplift": round(float(np.mean(preds.uplift)), 6),
    "std_uplift": round(float(np.std(preds.uplift)), 6),
    "min_uplift": round(float(np.min(preds.uplift)), 6),
    "max_uplift": round(float(np.max(preds.uplift)), 6),
    "sample_uplifts": [round(float(u), 6) for u in preds.uplift[:5]],
}}

print(json.dumps(fresh_scores))
"""

    res = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    fresh_scores = json.loads(res.stdout.strip())

    assert fresh_scores["n_fixture_rows"] == saved_smoke["n_fixture_rows"]
    assert pytest.approx(fresh_scores["mean_p_treat"], abs=1e-5) == saved_smoke["mean_p_treat"]
    assert pytest.approx(fresh_scores["mean_p_control"], abs=1e-5) == saved_smoke["mean_p_control"]
    assert pytest.approx(fresh_scores["mean_uplift"], abs=1e-5) == saved_smoke["mean_uplift"]
    assert pytest.approx(fresh_scores["std_uplift"], abs=1e-5) == saved_smoke["std_uplift"]
    assert pytest.approx(fresh_scores["min_uplift"], abs=1e-5) == saved_smoke["min_uplift"]
    assert pytest.approx(fresh_scores["max_uplift"], abs=1e-5) == saved_smoke["max_uplift"]
    assert fresh_scores["sample_uplifts"] == saved_smoke["sample_uplifts"]
