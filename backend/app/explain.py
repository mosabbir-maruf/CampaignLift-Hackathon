"""Top-level explain package re-export for CampaignLift backend.

Canonical planning sources:
- planning/backend_plan.md
- tasks/assaduzzaman/21_explanation_api.md
"""

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
