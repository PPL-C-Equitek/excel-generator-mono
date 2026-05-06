EXTRACTION_TOP_LEVEL_KEYS = ("document_info", "summary", "content_data")
NORMALIZED_TABLE_COLUMNS = (
  "unit",
  "item",
  "num_type",
  "status_type",
  "value",
)

EXTRACTION_TOP_LEVEL_KEYS_TEXT = ", ".join(EXTRACTION_TOP_LEVEL_KEYS)
NORMALIZED_TABLE_COLUMNS_TEXT = "\n".join(
  [f'  "{column}",' for column in NORMALIZED_TABLE_COLUMNS[:-1]]
  + [f'  "{NORMALIZED_TABLE_COLUMNS[-1]}"']
)

ROLE_SECTION = """## ROLE
You are a document parsing assistant.

Return ONLY a valid JSON object.
No markdown, no code fences, and no explanation.
"""

TASK_SECTION = """## TASK
Parse the uploaded document content and return the actual extracted data only.

The JSON object must have exactly three top-level keys:
- document_info
- summary
- content_data

Do not return example or placeholder data.
Do not fabricate rows, fields, or values.
"""

QUALITY_SECTION = """## QUALITY_RULES
### Output Contract
- top-level keys must be exactly: {top_level_keys}
- document_info.source_type must be exactly: Excel or PDF (case-sensitive)
- document_info.filename must be a non-empty string

### Summary Rules
- summary must be an object
- summary keys must be non-empty strings
- summary values must be scalar only: string, number, boolean, or null
- no arrays and no nested objects

### Content Data Rules
- content_data must be a non-empty array
- each table must include:
  - table_name: non-empty string and unique across content_data
  - headers: non-empty array of unique non-empty strings
  - rows: array of objects
- each row object must use keys that match headers exactly
- row values must be scalar only: string, number, boolean, or null
- no nested objects and no nested arrays in rows

### Source-Specific Rules
- Excel: if multiple sheets exist, each sheet must be a separate table in content_data
- Excel: table_name must use the real sheet name
- Excel: do not merge sheets together
- PDF: combine all extracted content into a single table object in content_data regardless of page count

### Normalization / Unpivot Rules
If columns represent categorical groupings (department names, regions, units, or similar),
unpivot those columns into long-format rows.

The normalized table must use these exact column names:
[
{normalized_table_columns}
]

Never use translated or alternative names such as:
- Nilai
- Tipe
- Status
- Item as a source header label
- any other language variant

Exclude rows where value is 0 or null after unpivoting.

### Reliability
- always return data derived from the real uploaded content
- infer conservatively when data is unclear
- keep output internally consistent and schema compliant
""".format(
  top_level_keys=EXTRACTION_TOP_LEVEL_KEYS_TEXT,
  normalized_table_columns=NORMALIZED_TABLE_COLUMNS_TEXT,
)

INPUT_SECTION_TEMPLATE = """## INPUT
{sanitized_user_input}
"""


def _neutralize_control_markers(value: str) -> str:
    return value.replace("##", "＃＃")


def sanitize_user_input(user_input: str) -> str:
    if not isinstance(user_input, str):
        raise ValueError("user_input must be a string.")

    cleaned = user_input.strip()
    if not cleaned:
        return "[EMPTY_INPUT]"

    return _neutralize_control_markers(cleaned)
