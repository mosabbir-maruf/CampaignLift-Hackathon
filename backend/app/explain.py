"""Top-level explain package re-export for CampaignLift backend."""

from backend.app.services.explain import (
    CustomerNotFoundError,
    clean_feature_name,
    determine_reason_code,
    ensure_explain_db_schema,
    explain_customer,
    extract_feature_contributions,
    generate_template_text,
)

__all__ = [
    "CustomerNotFoundError",
    "clean_feature_name",
    "determine_reason_code",
    "ensure_explain_db_schema",
    "explain_customer",
    "extract_feature_contributions",
    "generate_template_text",
]
