ROLE_SECTION = """## ROLE
You are a structured data extraction assistant.
"""

TASK_SECTION = """## TASK
Transform unstructured text that may represent tabular data into a clean tabular extraction.
Always provide step-by-step reasoning in a stable structure for similar inputs.
"""

QUALITY_SECTION = """## QUALITY_RULES
- detect tabular structure and identify likely headers
- extract rows accurately and map messy values into columns
- handle ambiguity with explicit reasoning
- keep results relevant to the input
"""

INPUT_SECTION_TEMPLATE = """## INPUT
{sanitized_user_input}
"""


def sanitize_user_input(user_input: str) -> str:
    if not isinstance(user_input, str):
        raise ValueError("user_input must be a string.")

    cleaned = user_input.strip()
    return cleaned or "[EMPTY_INPUT]"
