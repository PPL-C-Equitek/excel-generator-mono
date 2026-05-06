import json
from typing import Any

from .base import EXTRACTION_TOP_LEVEL_KEYS, NORMALIZED_TABLE_COLUMNS


MAX_REASONING_CONTEXT_CHARS = 12000

EXTRACTION_OUTPUT_SCHEMA_KEYS = list(EXTRACTION_TOP_LEVEL_KEYS)

EXTRACTION_OUTPUT_SCHEMA_KEYS_TEXT = ", ".join(EXTRACTION_OUTPUT_SCHEMA_KEYS)
NORMALIZED_TABLE_COLUMNS_TEXT = "\n".join(
    [f'  "{column}",' for column in NORMALIZED_TABLE_COLUMNS[:-1]]
    + [f'  "{NORMALIZED_TABLE_COLUMNS[-1]}"']
)

OUTPUT_FORMAT_SECTION = """## OUTPUT_FORMAT
Return ONLY valid JSON object with exactly these keys:
- {top_level_keys}

Required structure:
- document_info.source_type: "Excel" or "PDF" (case-sensitive)
- document_info.filename: non-empty string
- summary: object with non-empty string keys and scalar values only
- content_data[*].table_name: non-empty unique string
- content_data[*].headers: non-empty unique string array
- content_data[*].rows: array of objects with keys matching headers exactly

Rules:
- no markdown
- no code fences
- no extra explanation outside JSON
- no top-level keys besides: document_info, summary, content_data
- no nested objects/arrays inside summary values or row cell values
-""".format(
  top_level_keys="\n- ".join(f'"{key}"' for key in EXTRACTION_OUTPUT_SCHEMA_KEYS),
)

AMBIGUOUS_CASE_SECTION = """## AMBIGUOUS_CASE
If extraction is ambiguous or insufficient:
- keep the same required output contract
- never switch to free-form text
- do not invent values
- use conservative scalar values such as null only for optional fields when needed
- keep required tables and required arrays populated from the source instead of fabricating empty placeholders
"""

MESSY_RECOVERABLE_CASE_SECTION = """## MESSY_BUT_RECOVERABLE
If input is messy but recoverable:
- infer likely headers
- normalize values
- preserve row consistency
- map values into the correct table and column context
- keep schema compliance while maximizing extracted signal from the input
"""


def _to_json_context(value: Any, max_chars: int = MAX_REASONING_CONTEXT_CHARS) -> str:
  try:
    serialized = json.dumps(value, ensure_ascii=True)
  except (TypeError, ValueError):
    serialized = str(value)

  if len(serialized) <= max_chars:
    return serialized

  return f"{serialized[:max_chars]}... [TRUNCATED]"


def build_conversion_reasoning_prompt(
  input_json: dict[str, Any] | list[Any],
  output_json: dict[str, Any] | list[Any],
  file_name: str = "unknown",
  document_type: str = "unknown",
) -> str:
  input_context = _to_json_context(input_json)
  output_context = _to_json_context(output_json)

  return (
    "Explain the conversion from input document data to extracted JSON output. "
    "Return concise, safe, user-facing reasoning only.\n\n"
    "CONTEXT:\n"
    f"- file_name: {file_name}\n"
    f"- document_type: {document_type}\n\n"
    "INPUT_JSON:\n"
    f"{input_context}\n\n"
    "OUTPUT_JSON:\n"
    f"{output_context}\n\n"
    "GOAL:\n"
    "1) Explain why key mapping/header decisions were chosen.\n"
    "2) Highlight ambiguity and assumptions.\n"
    "3) Summarize confidence level in the conversion result."
  )
