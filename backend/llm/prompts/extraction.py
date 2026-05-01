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


def _build_chat_context_section(chat_context: str | None) -> str | None:
    normalized = chat_context.strip() if isinstance(chat_context, str) else ""
    if not normalized:
        return None

    return (
        "## CHAT_CONTEXT\n"
        "The user has provided specific instructions via chat before converting. "
        "Apply these instructions strictly during extraction. "
        "These instructions take priority over default behavior.\n"
        f"{normalized}"
    )


def build_extraction_prompt(
    schema_hint: str | None = None,
    chat_context: str | None = None,
) -> str:
    sections = [BASE_EXTRACTION_PROMPT]

    schema_hint_section = _build_schema_hint_section(schema_hint)
    if schema_hint_section:
        sections.append(schema_hint_section.strip())

    chat_context_section = _build_chat_context_section(chat_context)
    if chat_context_section:
        sections.append(chat_context_section.strip())

    return "\n\n".join(sections)
