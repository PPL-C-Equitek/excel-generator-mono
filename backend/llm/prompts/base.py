ROLE_SECTION = """## ROLE
You are a precise data extraction specialist.
Your job is to transform unstructured or semi-structured text into clean, structured tabular data.
You prioritize accuracy and consistency. You flag ambiguities rather than guessing.
You treat headers and data types seriously—consistency across rows matters.
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


def _neutralize_control_markers(value: str) -> str:
    return value.replace("##", "＃＃")


def sanitize_user_input(user_input: str) -> str:
    if not isinstance(user_input, str):
        raise ValueError("user_input must be a string.")

    cleaned = user_input.strip()
    if not cleaned:
        return "[EMPTY_INPUT]"

    return _neutralize_control_markers(cleaned)
