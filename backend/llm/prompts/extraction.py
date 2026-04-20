from .base import (
    INPUT_SECTION_TEMPLATE,
    QUALITY_SECTION,
    ROLE_SECTION,
    TASK_SECTION,
    sanitize_user_input,
)
from .schemas import (
    AMBIGUOUS_CASE_SECTION,
    MESSY_RECOVERABLE_CASE_SECTION,
    OUTPUT_FORMAT_SECTION,
)


def _build_schema_hint_section(schema_hint: str | None) -> str | None:
    normalized_schema_hint = schema_hint.strip() if isinstance(schema_hint, str) else ""
    if not normalized_schema_hint:
        return None

    return (
        "## SCHEMA_HINT\n"
        "Prioritize schema-defined fields when mapping headers and rows.\n"
        "If input conflicts with schema, prefer schema field names and explain reconciliation in reasoning_steps.\n"
        f"Schema guidance:\n{normalized_schema_hint}"
    )


def build_extraction_prompt(user_input: str, schema_hint: str | None = None) -> str:
    sanitized_user_input = sanitize_user_input(user_input)
    schema_hint_section = _build_schema_hint_section(schema_hint)

    sections = [
        ROLE_SECTION.strip(),
        TASK_SECTION.strip(),
        OUTPUT_FORMAT_SECTION.strip(),
        QUALITY_SECTION.strip(),
        AMBIGUOUS_CASE_SECTION.strip(),
        MESSY_RECOVERABLE_CASE_SECTION.strip(),
    ]

    if schema_hint_section:
        sections.append(schema_hint_section.strip())

    sections.extend([
        INPUT_SECTION_TEMPLATE.format(sanitized_user_input=sanitized_user_input).strip(),
    ])

    return "\n\n".join(sections)
