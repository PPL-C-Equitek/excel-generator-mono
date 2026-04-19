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


def build_extraction_prompt(user_input: str) -> str:
    sanitized_user_input = sanitize_user_input(user_input)

    sections = [
        ROLE_SECTION.strip(),
        TASK_SECTION.strip(),
        OUTPUT_FORMAT_SECTION.strip(),
        QUALITY_SECTION.strip(),
        AMBIGUOUS_CASE_SECTION.strip(),
        MESSY_RECOVERABLE_CASE_SECTION.strip(),
        INPUT_SECTION_TEMPLATE.format(sanitized_user_input=sanitized_user_input).strip(),
    ]

    return "\n\n".join(sections)
