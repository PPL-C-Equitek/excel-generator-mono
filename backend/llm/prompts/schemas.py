import json
from typing import Any


MAX_REASONING_CONTEXT_CHARS = 12000
MAX_REASONING_TABLES = 5
MAX_REASONING_HEADERS = 20
MAX_REASONING_KEY_SAMPLE = 20
MAX_REASONING_TEXT_PREVIEW_CHARS = 300

EXTRACTION_OUTPUT_SCHEMA_KEYS = [
  "document_info",
  "summary",
  "content_data",
]

OUTPUT_FORMAT_SECTION = """## OUTPUT_FORMAT
Return ONLY valid JSON object with exactly these keys:
- "document_info" (object)
- "summary" (object)
- "content_data" (non-empty array of table objects)

Required structure:
- document_info.source_type: "Excel", "PDF", "DOCX", "CSV", "TXT", or "Image" (case-sensitive)
- document_info.filename: non-empty string
- summary: object with non-empty string keys and scalar values only
- content_data[*].table_name: non-empty unique string
- content_data[*].headers: non-empty unique string array
- content_data[*].rows: array of objects with keys matching headers exactly
- if the source contains multiple distinct tables, output multiple content_data entries in source order
- do not merge separate tables into a single content_data entry unless they are clearly the same table continued across pages

Rules:
- no markdown
- no code fences
- no extra explanation outside JSON
- no top-level keys besides: document_info, summary, content_data
- no nested objects/arrays inside summary values or row cell values
"""

AMBIGUOUS_CASE_SECTION = """## AMBIGUOUS_CASE
If extraction is ambiguous or insufficient:
- keep the same required output contract
- never switch to free-form text
- do not invent values
- use conservative scalar values and empty collections only when truly unsupported by the input
"""

MESSY_RECOVERABLE_CASE_SECTION = """## MESSY_BUT_RECOVERABLE
If input is messy but recoverable:
- infer likely headers
- normalize values
- preserve row consistency
- map values into the correct table and column context
- keep schema compliance while maximizing extracted signal from the input
"""


def _truncate_text(value: Any, max_chars: int = MAX_REASONING_TEXT_PREVIEW_CHARS) -> str | None:
  if not isinstance(value, str):
    return None

  trimmed = value.strip()
  if not trimmed:
    return None
  if len(trimmed) <= max_chars:
    return trimmed
  return f"{trimmed[:max_chars]}... [TRUNCATED]"


def _stringify_sample(values: list[Any], max_items: int) -> list[str]:
  return [str(value) for value in values[:max_items]]


def _summarize_row_shape(row: Any) -> dict[str, Any]:
  if isinstance(row, dict):
    keys = list(row.keys())
    return {
      "row_type": "object",
      "key_count": len(keys),
      "key_sample": _stringify_sample(keys, MAX_REASONING_KEY_SAMPLE),
    }

  if isinstance(row, list):
    return {
      "row_type": "array",
      "column_count": len(row),
    }

  return {"row_type": type(row).__name__}


def _summarize_table(table: dict[str, Any], fallback_name: str) -> dict[str, Any]:
  table_name = table.get("table_name")
  normalized_name = (
    table_name.strip()
    if isinstance(table_name, str) and table_name.strip()
    else fallback_name
  )
  headers = table.get("headers")
  normalized_headers = headers if isinstance(headers, list) else []
  rows = table.get("rows")
  normalized_rows = rows if isinstance(rows, list) else []

  summary = {
    "table_name": normalized_name,
    "header_count": len(normalized_headers),
    "header_sample": _stringify_sample(normalized_headers, MAX_REASONING_HEADERS),
    "row_count": len(normalized_rows),
  }

  if normalized_rows:
    summary["first_row_shape"] = _summarize_row_shape(normalized_rows[0])

  return summary


def _summarize_scalar_object(value: Any) -> dict[str, Any] | None:
  if not isinstance(value, dict):
    return None

  summarized = {}
  for key, raw_value in value.items():
    if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
      if isinstance(raw_value, str):
        summarized[key] = _truncate_text(raw_value)
      else:
        summarized[key] = raw_value
    if len(summarized) >= MAX_REASONING_KEY_SAMPLE:
      break

  if not summarized:
    return None

  return summarized


def _summarize_tabular_payload(value: Any) -> dict[str, Any] | None:
  if not isinstance(value, dict):
    return None

  content_data = value.get("content_data")
  if not isinstance(content_data, list):
    return None

  tables: list[dict[str, Any]] = []
  for index, item in enumerate(content_data[:MAX_REASONING_TABLES]):
    if not isinstance(item, dict):
      continue
    tables.append(_summarize_table(item, fallback_name=f"Table{index + 1}"))

  summary = {
    "kind": "tabular_output",
    "table_count": len(content_data),
    "tables": tables,
  }

  if len(content_data) > MAX_REASONING_TABLES:
    summary["tables_omitted"] = len(content_data) - MAX_REASONING_TABLES

  summarized_document_info = _summarize_scalar_object(value.get("document_info"))
  if summarized_document_info:
    summary["document_info"] = summarized_document_info

  summarized_summary = _summarize_scalar_object(value.get("summary"))
  if summarized_summary:
    summary["summary"] = summarized_summary

  return summary


def _summarize_extracted_payload(extracted: Any) -> dict[str, Any]:
  if isinstance(extracted, dict):
    sheet_names = list(extracted.keys())
    sheets: list[dict[str, Any]] = []
    for sheet_name in sheet_names[:MAX_REASONING_TABLES]:
      sheet_rows = extracted.get(sheet_name)
      normalized_rows = sheet_rows if isinstance(sheet_rows, list) else []
      sheet_summary = {
        "sheet_name": sheet_name,
        "row_count": len(normalized_rows),
      }
      if normalized_rows:
        sheet_summary["first_row_shape"] = _summarize_row_shape(normalized_rows[0])
      sheets.append(sheet_summary)

    summarized = {
      "sheet_count": len(sheet_names),
      "sheets": sheets,
    }
    if len(sheet_names) > MAX_REASONING_TABLES:
      summarized["sheets_omitted"] = len(sheet_names) - MAX_REASONING_TABLES
    return summarized

  if isinstance(extracted, list):
    summarized = {"item_count": len(extracted)}
    if extracted:
      summarized["first_item_shape"] = _summarize_row_shape(extracted[0])
    return summarized

  return {"value_type": type(extracted).__name__}


def _summarize_upload_wrapper(value: dict[str, Any]) -> dict[str, Any]:
  summary: dict[str, Any] = {
    "kind": "upload_wrapper",
    "has_extracted": "extracted" in value,
  }

  filename = _truncate_text(value.get("filename"))
  if filename:
    summary["filename"] = filename

  format_value = _truncate_text(value.get("format"))
  if format_value:
    summary["format"] = format_value

  user_prompt = _truncate_text(value.get("user_prompt"))
  if user_prompt:
    summary["user_prompt"] = user_prompt

  summary["has_previous_output"] = isinstance(value.get("previous_output"), (dict, list))
  if summary["has_previous_output"]:
    previous_output_summary = _summarize_tabular_payload(value.get("previous_output"))
    if previous_output_summary is not None:
      summary["previous_output"] = previous_output_summary

  summary["extracted"] = _summarize_extracted_payload(value.get("extracted"))
  return summary


def _summarize_generic_payload(value: Any, kind: str) -> dict[str, Any]:
  if isinstance(value, dict):
    keys = list(value.keys())
    key_sample = _stringify_sample(keys, MAX_REASONING_KEY_SAMPLE)
    value_types = {
      str(key): type(raw_value).__name__
      for key, raw_value in list(value.items())[:MAX_REASONING_KEY_SAMPLE]
    }
    return {
      "kind": kind,
      "payload_type": "object",
      "key_count": len(keys),
      "key_sample": key_sample,
      "value_types": value_types,
    }

  if isinstance(value, list):
    item_types = []
    for item in value[:MAX_REASONING_KEY_SAMPLE]:
      item_type = type(item).__name__
      if item_type not in item_types:
        item_types.append(item_type)
    return {
      "kind": kind,
      "payload_type": "array",
      "item_count": len(value),
      "item_types": item_types,
    }

  return {
    "kind": kind,
    "payload_type": type(value).__name__,
  }


def _build_reasoning_context_summary(value: Any, kind: str) -> dict[str, Any]:
  if isinstance(value, dict) and "extracted" in value:
    return _summarize_upload_wrapper(value)

  tabular_summary = _summarize_tabular_payload(value)
  if tabular_summary is not None:
    return tabular_summary

  return _summarize_generic_payload(value, kind=kind)


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
  input_context = _to_json_context(
    _build_reasoning_context_summary(input_json, kind="input_context")
  )
  output_context = _to_json_context(
    _build_reasoning_context_summary(output_json, kind="output_context")
  )

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
