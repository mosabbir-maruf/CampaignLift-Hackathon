"""Top-level gemini package re-export for CampaignLift backend.

Canonical planning sources:
- planning/gemini_plan.md
- tasks/assaduzzaman/22_gemini_adapter.md
"""

from backend.app.services.gemini import (
    SYSTEM_INSTRUCTION,
    CopilotDisabledError,
    CopilotUnavailableError,
    RunNotFoundError,
    build_run_context,
    call_gemini_api,
    extract_customer_id_from_text,
    query_copilot,
)

__all__ = [
    "SYSTEM_INSTRUCTION",
    "CopilotDisabledError",
    "CopilotUnavailableError",
    "RunNotFoundError",
    "build_run_context",
    "call_gemini_api",
    "extract_customer_id_from_text",
    "query_copilot",
]
