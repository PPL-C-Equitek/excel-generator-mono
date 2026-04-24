EXTRACTION_OUTPUT_SCHEMA_KEYS = [
    "reasoning_steps",
    "headers",
    "rows",
    "final_answer",
]

OUTPUT_FORMAT_SECTION = """## OUTPUT_FORMAT
Return ONLY valid JSON object with exactly these keys:
- "reasoning_steps" (array of strings)
- "headers" (array of strings)
- "rows" (array of arrays)
- "final_answer" (string)
Rules:
- no markdown
- no code fences
- no extra explanation outside JSON
- no extra keys unless existing system requires them
"""

AMBIGUOUS_CASE_SECTION = """## AMBIGUOUS_CASE
If input is ambiguous or insufficient, return:
{
  "reasoning_steps": [
    "Input does not contain enough structured information."
  ],
  "headers": [],
  "rows": [],
  "final_answer": "Please provide clearer or more complete data."
}
"""

MESSY_RECOVERABLE_CASE_SECTION = """## MESSY_BUT_RECOVERABLE
If input is messy but recoverable:
- infer likely headers
- normalize values
- preserve row consistency
- explain mapping in reasoning_steps
"""
