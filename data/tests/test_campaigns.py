"""Tests for campaign generator module."""

from datetime import date
import json
from pathlib import Path
import sys
import jsonschema
import pytest

# Add data/src to sys.path
data_src = Path(__file__).resolve().parents[1] / "src"
if str(data_src) not in sys.path:
    sys.path.insert(0, str(data_src))

from campaignlift_data.campaigns import (
    DEFAULT_CAMPAIGN_START_DATE,
    get_current_campaign,
    get_prior_campaigns,
)
from campaignlift_data.config import load_world_config


@pytest.fixture
def campaign_schema():
    """Load canonical campaign schema."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "campaign.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_current_campaign_validates_against_schema(campaign_schema):
    """The single modeled current campaign validates against campaign.schema.json."""
    config = load_world_config()
    current = get_current_campaign(config)

    # Validate against JSON schema
    jsonschema.validate(instance=current, schema=campaign_schema)

    # Validate key fields
    assert current["campaign_id"] == "CMP2024_QR01"
    assert current["objective"] == config["eligibility"]["default_demo_objective"]
    assert current["start_date"] == DEFAULT_CAMPAIGN_START_DATE.isoformat()
    assert current["outcome_window_days"] == config["timeline"]["outcome_window_days"]
    assert current["incentive_cost_bdt"] >= 0.0


def test_prior_campaign_end_dates_strictly_before_assigned_at(campaign_schema):
    """All prior campaign end dates are strictly before assigned_at."""
    config = load_world_config()
    assigned_date = DEFAULT_CAMPAIGN_START_DATE
    priors = get_prior_campaigns(config, assigned_date=assigned_date)

    assert len(priors) > 0, "Expected at least one prior campaign stub"

    campaign_ids = set()
    for camp in priors:
        # Validate against JSON schema
        jsonschema.validate(instance=camp, schema=campaign_schema)

        # Enforce end_date strictly before assigned_date
        end_d = date.fromisoformat(camp["end_date"])
        assert end_d < assigned_date, (
            f"Prior campaign {camp['campaign_id']} end_date {end_d} is >= assigned_date {assigned_date}"
        )

        # Unique IDs
        assert camp["campaign_id"] not in campaign_ids
        campaign_ids.add(camp["campaign_id"])

        # Cost non-negative
        assert camp["incentive_cost_bdt"] >= 0.0


def test_prior_campaigns_do_not_contain_current_modeled_campaign():
    """Prior campaign IDs must not collide with the current modeled campaign ID."""
    current = get_current_campaign()
    priors = get_prior_campaigns()

    prior_ids = {p["campaign_id"] for p in priors}
    assert current["campaign_id"] not in prior_ids


def test_negative_campaign_schema_rejection(campaign_schema):
    """Negative test: Campaigns violating schema constraints fail validation."""
    current = get_current_campaign()

    # 1. Invalid objective
    bad_obj = dict(current, objective="invalid_objective")
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_obj, schema=campaign_schema)

    # 2. Negative incentive cost
    bad_cost = dict(current, incentive_cost_bdt=-5.0)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_cost, schema=campaign_schema)

    # 3. Missing required field (campaign_id)
    bad_missing = dict(current)
    del bad_missing["campaign_id"]
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=bad_missing, schema=campaign_schema)
