from .base import (
    QUALITY_SECTION,
    ROLE_SECTION,
    TASK_SECTION,
)
from .schemas import (
    AMBIGUOUS_CASE_SECTION,
    MESSY_RECOVERABLE_CASE_SECTION,
    OUTPUT_FORMAT_SECTION,
)

BASE_EXTRACTION_PROMPT = "\n\n".join(
    [
        ROLE_SECTION.strip(),
        TASK_SECTION.strip(),
        OUTPUT_FORMAT_SECTION.strip(),
        QUALITY_SECTION.strip(),
        AMBIGUOUS_CASE_SECTION.strip(),
        MESSY_RECOVERABLE_CASE_SECTION.strip(),
    ]
)


def _build_schema_hint_section(schema_hint: str | None) -> str | None:
    normalized_schema_hint = schema_hint.strip() if isinstance(schema_hint, str) else ""
    if not normalized_schema_hint:
        return None

    return (
        "## SCHEMA_HINT\n"
        "Prioritize schema-defined fields for headers and row mapping.\n"
        f"Schema guidance:\n{normalized_schema_hint}"
    )


def build_extraction_prompt(schema_hint: str | None = None) -> str:
    schema_hint_section = _build_schema_hint_section(schema_hint)
    if not schema_hint_section:
        return BASE_EXTRACTION_PROMPT

    return f"{BASE_EXTRACTION_PROMPT}\n\n{schema_hint_section.strip()}"
