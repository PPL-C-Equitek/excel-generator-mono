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


def _build_chat_context_section(chat_context: str | None) -> str | None:
    normalized = chat_context.strip() if isinstance(chat_context, str) else ""
    if not normalized:
        return None

    return (
        "## CHAT_CONTEXT\n"
        "The user has provided specific instructions via chat before converting. "
        "Apply these instructions strictly during extraction when they do not conflict with the output contract. "
        "These instructions can refine interpretation, but they must never override schema rules, source-specific rules, or JSON-only output constraints.\n"
        f"{normalized}"
    )


def _build_ocr_context_section(ocr_context: dict | str | None) -> str | None:
    if isinstance(ocr_context, str):
        normalized = ocr_context.strip()
        if not normalized:
            return None
        return (
            "## OCR_QUALITY_CONTEXT\n"
            "OCR quality metadata provided by the extraction pipeline.\n"
            f"{normalized}"
        )

    if not isinstance(ocr_context, dict) or not ocr_context:
        return None

    confidence_score = ocr_context.get("confidence_score")
    confidence_level = ocr_context.get("confidence_level", "unknown")
    document_type = ocr_context.get("document_type", "unknown")
    processing_method = ocr_context.get("processing_method")
    corrections_applied = ocr_context.get("corrections_applied") or []
    low_confidence_regions = ocr_context.get("low_confidence_regions") or []

    lines = [
        "## OCR_QUALITY_CONTEXT",
        f"Document Type: {document_type}",
        f"OCR Confidence: {confidence_score if confidence_score is not None else 'unknown'}% ({confidence_level})",
        "",
        "Confidence Levels:",
        "- Low (0-40%): Text is unclear; interpret liberally",
        "- Medium (40-75%): Probably correct but accept variations",
        "- High (75%+): Very likely correct",
    ]

    if processing_method:
        lines.extend(["", f"Processing Method: {processing_method}"])

    if low_confidence_regions:
        lines.extend(["", "Low-Confidence Regions (first 5):"])
        for region in low_confidence_regions[:5]:
            if isinstance(region, dict):
                text = region.get("text", "")
                confidence = region.get("confidence", "unknown")
                lines.append(f"- '{text}' ({confidence}%)")

    lines.extend(["", f"Corrections Applied: {len(corrections_applied)}"])
    return "\n".join(lines)


def build_extraction_prompt(
    schema_hint: str | None = None,
    refinement_instruction: str | None = None,
    chat_context: str | None = None,
    ocr_context: dict | str | None = None,
) -> str:
    sections = [BASE_EXTRACTION_PROMPT]

    schema_hint_section = _build_schema_hint_section(schema_hint)
    if schema_hint_section:
        sections.append(schema_hint_section.strip())

    ocr_context_section = _build_ocr_context_section(ocr_context)
    if ocr_context_section:
        sections.append(ocr_context_section.strip())

    chat_context_section = _build_chat_context_section(chat_context)
    if chat_context_section:
        sections.append(chat_context_section.strip())

    refinement_section = _build_refinement_section(refinement_instruction)
    if refinement_section:
        sections.append(refinement_section.strip())

    return "\n\n".join(sections)
