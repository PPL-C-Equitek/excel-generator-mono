import json
from typing import Any


MAX_REASONING_CONTEXT_CHARS = 12000

EXTRACTION_OUTPUT_SCHEMA_KEYS = [
  "headers",
  "rows",
]

OUTPUT_FORMAT_SECTION = """## OUTPUT_FORMAT
Return ONLY valid JSON object with exactly these keys:
- "headers" (array of strings)
- "rows" (array of arrays)
Rules:
- no markdown
- no code fences
- no extra explanation outside JSON
- no extra keys unless existing system requires them
"""

AMBIGUOUS_CASE_SECTION = """## AMBIGUOUS_CASE
If input is ambiguous or insufficient, return:
{
  "headers": [],
  "rows": []
}
"""

MESSY_RECOVERABLE_CASE_SECTION = """## MESSY_BUT_RECOVERABLE
If input is messy but recoverable:
- infer likely headers
- normalize values
- preserve row consistency
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
