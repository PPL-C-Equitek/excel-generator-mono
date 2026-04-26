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


def _build_refinement_section(refinement_instruction: str | None) -> str | None:
    normalized_instruction = (
        refinement_instruction.strip() if isinstance(refinement_instruction, str) else ""
    )
    if not normalized_instruction:
        return None

    return (
        "## REFINEMENT\n"
        "This is a refinement attempt based on validation feedback.\n"
        "Fix only schema or validation violations while preserving extracted meaning.\n"
        "Do not include explanations in output.\n"
        f"{normalized_instruction}"
    )


def build_extraction_prompt(
    schema_hint: str | None = None,
    refinement_instruction: str | None = None,
) -> str:
    schema_hint_section = _build_schema_hint_section(schema_hint)
    refinement_section = _build_refinement_section(refinement_instruction)
    if not schema_hint_section and not refinement_section:
        return BASE_EXTRACTION_PROMPT

    prompt_sections = [BASE_EXTRACTION_PROMPT]
    if schema_hint_section:
        prompt_sections.append(schema_hint_section.strip())
    if refinement_section:
        prompt_sections.append(refinement_section.strip())
    return "\n\n".join(prompt_sections)
