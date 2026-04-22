import json
import re
from typing import Any, Callable, Protocol

from django.conf import settings

from .openai_client import OpenAIServiceError


DEFAULT_REASONING_OUTPUT_TEXT_MAX_CHARS = 120000
DEFAULT_REASONING_FINAL_ANSWER_MAX_CHARS = 4000
DEFAULT_REASONING_THINKING_LOG_MAX_CHARS = 16000
DEFAULT_REASONING_STEP_MAX_CHARS = 2000
DEFAULT_REASONING_STEPS_MAX_ITEMS = 20

FALLBACK_FINAL_ANSWER = "Unable to parse final answer from model output."
FALLBACK_REASONING_STEP = "Unable to parse structured reasoning steps from model output."
FALLBACK_THINKING_LOG = "Unable to parse thinking log from model output."

FINAL_ANSWER_LABELS = {"final answer", "answer", "conclusion"}
THINKING_LOG_LABELS = {
    "thinking log",
    "thinking",
    "reasoning",
    "analysis",
    "thought process",
}
STEP_SECTION_HEADERS = {"reasoning step", "reasoning steps", "step", "steps", "analysis"}
STEP_PREFIX_TOKEN = "step"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

ReasoningLimits = tuple[int, int, int, int, int]


class TextGenerationProvider(Protocol):
    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str: ...


def get_base_system_prompt() -> str:
    raw_prompt = getattr(settings, "OPENAI_SYSTEM_PROMPT", "")
    if not isinstance(raw_prompt, str):
        return ""
    return raw_prompt.strip()


def get_reasoning_system_prompt() -> str:
    return (
        "Return a valid JSON object with exactly these keys: "
        '"final_answer" (string), "reasoning_steps" (array of non-empty strings), '
        'and "thinking_log" (string). Do not wrap the JSON in markdown or code fences. '
        "Keep reasoning concise, safe for display, and do not reveal hidden chain-of-thought."
    )


def compose_system_prompt(
    base_prompt: str | None,
    schema_prompt_fragment: str | None = None,
) -> str | None:
    parts: list[str] = []

    normalized_base_prompt = base_prompt.strip() if isinstance(base_prompt, str) else ""
    if normalized_base_prompt:
        parts.append(normalized_base_prompt)

    normalized_schema_prompt = (
        schema_prompt_fragment.strip()
        if isinstance(schema_prompt_fragment, str)
        else ""
    )
    if normalized_schema_prompt:
        parts.append(normalized_schema_prompt)

    if not parts:
        return None

    return "\n\n".join(parts)


def _normalize_prompt(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("prompt must be a non-empty string.")
    return value.strip()


def _get_positive_int_setting(setting_name: str, default_value: int) -> int:
    raw_value = getattr(settings, setting_name, default_value)
    if isinstance(raw_value, int) and raw_value > 0:
        return raw_value
    return default_value


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars]


def _normalize_reasoning_text(value: Any, field_name: str, max_chars: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpenAIServiceError(
            f"OpenAI reasoning response must include {field_name} as a non-empty string."
        )
    return _truncate_text(value.strip(), max_chars)


def _try_parse_json_candidate(text: str) -> Any | None:
    if not isinstance(text, str) or not text.strip():
        return None

    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _consume_spaces_or_tabs(text: str, index: int) -> int:
    text_length = len(text)
    while index < text_length and text[index] in " \t":
        index += 1
    return index


def _consume_language_token(text: str, index: int) -> tuple[str, int]:
    text_length = len(text)
    token_start = index
    while index < text_length and (text[index].isalnum() or text[index] in "_-"):
        index += 1
    return text[token_start:index].strip().lower(), index


def _consume_optional_newline(text: str, index: int) -> int:
    text_length = len(text)
    if index >= text_length or text[index] not in "\r\n":
        return index

    if text[index] == "\r" and index + 1 < text_length and text[index + 1] == "\n":
        return index + 2

    return index + 1


def _extract_fenced_block_metadata(text: str, fence_start: int) -> tuple[str, int]:
    index = _consume_spaces_or_tabs(text, fence_start + 3)
    language, index = _consume_language_token(text, index)
    index = _consume_spaces_or_tabs(text, index)
    index = _consume_optional_newline(text, index)
    return language, index


def _extract_json_from_fenced_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    text_length = len(text)

    while cursor < text_length:
        fence_start = text.find("```", cursor)
        if fence_start == -1:
            break

        language, index = _extract_fenced_block_metadata(text, fence_start)

        fence_end = text.find("```", index)
        if fence_end == -1:
            break

        if language in ("", "json"):
            candidate = text[index:fence_end].strip()
            if candidate:
                blocks.append(candidate)

        cursor = fence_end + 3

    return blocks


def _extract_braced_json_candidate(text: str) -> str | None:
    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return None

    candidate = text[start_index : end_index + 1].strip()
    return candidate or None


def _split_non_empty_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if isinstance(line, str) and line.strip()
    ]


def _split_labeled_line(line: str) -> tuple[str, str] | tuple[None, None]:
    for separator in (":", "-"):
        separator_index = line.find(separator)
        if separator_index <= 0:
            continue

        label = " ".join(line[:separator_index].strip().lower().split())
        value = line[separator_index + 1 :].strip()
        if label:
            return label, value

    return None, None


def _extract_labeled_value(line: str, allowed_labels: set[str]) -> str | None:
    label, value = _split_labeled_line(line)
    if label in allowed_labels and value:
        return value
    return None


def _is_step_section_header(line: str) -> bool:
    candidate = line.strip().rstrip(":-").strip().lower()
    normalized = " ".join(candidate.split())
    return normalized in STEP_SECTION_HEADERS


def _consume_whitespace(text: str, index: int) -> int:
    text_length = len(text)
    while index < text_length and text[index].isspace():
        index += 1
    return index


def _consume_digits(text: str, index: int) -> tuple[int, int]:
    text_length = len(text)
    start = index
    while index < text_length and text[index].isdigit():
        index += 1
    return start, index


def _consume_step_delimiters(text: str, index: int) -> int:
    text_length = len(text)
    while index < text_length and text[index] in ":.-)":
        index += 1
    return index


def _extract_bullet_step_text(stripped_line: str) -> str | None:
    if not stripped_line or stripped_line[0] not in "-*•":
        return None

    step_text = stripped_line[1:].lstrip()
    return step_text or None


def _extract_step_keyword_text(stripped_line: str) -> str | None:
    if not stripped_line.lower().startswith(STEP_PREFIX_TOKEN):
        return None

    cursor = _consume_whitespace(stripped_line, len(STEP_PREFIX_TOKEN))
    digit_start, cursor = _consume_digits(stripped_line, cursor)
    if cursor == digit_start:
        return None

    cursor = _consume_step_delimiters(stripped_line, cursor)
    cursor = _consume_whitespace(stripped_line, cursor)
    step_text = stripped_line[cursor:].strip()
    return step_text or None


def _extract_numbered_step_text(stripped_line: str) -> str | None:
    cursor_start, cursor = _consume_digits(stripped_line, 0)
    if cursor == cursor_start:
        return None

    cursor = _consume_whitespace(stripped_line, cursor)
    if cursor >= len(stripped_line) or stripped_line[cursor] not in ".)-":
        return None

    cursor = _consume_whitespace(stripped_line, cursor + 1)
    step_text = stripped_line[cursor:].strip()
    return step_text or None


def _extract_step_text(line: str) -> str | None:
    stripped_line = line.strip()
    if not stripped_line:
        return None

    step_text = _extract_bullet_step_text(stripped_line)
    if step_text is not None:
        return step_text

    step_text = _extract_step_keyword_text(stripped_line)
    if step_text is not None:
        return step_text

    return _extract_numbered_step_text(stripped_line)


def _is_reasoning_control_line(line: str) -> bool:
    final_answer_value = _extract_labeled_value(line, FINAL_ANSWER_LABELS)
    thinking_log_value = _extract_labeled_value(line, THINKING_LOG_LABELS)
    return final_answer_value is not None or thinking_log_value is not None


def _append_truncated_step(
    steps: list[str],
    step_text: str,
    max_steps: int,
    max_step_chars: int,
) -> bool:
    step = _truncate_text(step_text, max_step_chars)
    if step:
        steps.append(step)
    return len(steps) >= max_steps


def _try_append_explicit_step(
    steps: list[str],
    line: str,
    max_steps: int,
    max_step_chars: int,
) -> tuple[bool, bool]:
    step_text = _extract_step_text(line)
    if step_text is None:
        return False, False

    reached_limit = _append_truncated_step(steps, step_text, max_steps, max_step_chars)
    return True, reached_limit


def _collect_steps_from_lines(lines: list[str], max_steps: int, max_step_chars: int) -> list[str]:
    steps: list[str] = []
    inside_step_section = False

    for line in lines:
        if _is_step_section_header(line):
            inside_step_section = True
            continue

        found_explicit_step, reached_limit = _try_append_explicit_step(
            steps,
            line,
            max_steps,
            max_step_chars,
        )
        if found_explicit_step:
            if reached_limit:
                break
            continue

        if not (inside_step_section and line):
            continue

        if _is_reasoning_control_line(line):
            inside_step_section = False
            continue

        if _append_truncated_step(steps, line, max_steps, max_step_chars):
            break

    return steps


def _fallback_narrative_steps(text: str, max_steps: int, max_step_chars: int) -> list[str]:
    sentences = SENTENCE_SPLIT_RE.split(text.strip())
    steps: list[str] = []
    for sentence in sentences:
        normalized_sentence = sentence.strip()
        if not normalized_sentence:
            continue

        steps.append(_truncate_text(normalized_sentence, max_step_chars))
        if len(steps) >= max_steps:
            break

    if not steps and text.strip():
        steps.append(_truncate_text(text.strip(), max_step_chars))

    return steps


def _resolve_reasoning_limits() -> ReasoningLimits:
    max_output_chars = _get_positive_int_setting(
        "LLM_REASONING_OUTPUT_TEXT_MAX_CHARS",
        DEFAULT_REASONING_OUTPUT_TEXT_MAX_CHARS,
    )
    max_steps = _get_positive_int_setting(
        "LLM_REASONING_STEPS_MAX_ITEMS",
        DEFAULT_REASONING_STEPS_MAX_ITEMS,
    )
    max_step_chars = _get_positive_int_setting(
        "LLM_REASONING_STEP_MAX_CHARS",
        DEFAULT_REASONING_STEP_MAX_CHARS,
    )
    max_final_answer_chars = _get_positive_int_setting(
        "LLM_REASONING_FINAL_ANSWER_MAX_CHARS",
        DEFAULT_REASONING_FINAL_ANSWER_MAX_CHARS,
    )
    max_thinking_log_chars = _get_positive_int_setting(
        "LLM_REASONING_THINKING_LOG_MAX_CHARS",
        DEFAULT_REASONING_THINKING_LOG_MAX_CHARS,
    )
    return (
        max_output_chars,
        max_steps,
        max_step_chars,
        max_final_answer_chars,
        max_thinking_log_chars,
    )


def _normalize_raw_reasoning_output(raw_output: Any, max_output_chars: int) -> str:
    if isinstance(raw_output, str):
        normalized = raw_output.strip()
    else:
        normalized = str(raw_output or "").strip()
    return _truncate_text(normalized, max_output_chars)


def _fallback_empty_reasoning_response(
    max_final_answer_chars: int,
    max_step_chars: int,
    max_thinking_log_chars: int,
) -> dict[str, Any]:
    return {
        "final_answer": _truncate_text(FALLBACK_FINAL_ANSWER, max_final_answer_chars),
        "reasoning_steps": [_truncate_text(FALLBACK_REASONING_STEP, max_step_chars)],
        "thinking_log": _truncate_text(FALLBACK_THINKING_LOG, max_thinking_log_chars),
    }


def _parse_structured_reasoning_object(
    safe_text: str,
    skip_direct_json_parse: bool = False,
) -> dict[str, Any] | None:
    if not skip_direct_json_parse:
        direct_json = _try_parse_json_candidate(safe_text)
        if isinstance(direct_json, dict):
            return direct_json

    for candidate in _extract_json_from_fenced_blocks(safe_text):
        parsed_candidate = _try_parse_json_candidate(candidate)
        if isinstance(parsed_candidate, dict):
            return parsed_candidate

    braced_candidate = _extract_braced_json_candidate(safe_text)
    if braced_candidate is None:
        return None

    parsed_candidate = _try_parse_json_candidate(braced_candidate)
    if isinstance(parsed_candidate, dict):
        return parsed_candidate

    return None


def _extract_reasoning_fields_from_lines(
    lines: list[str],
    max_final_answer_chars: int,
    max_thinking_log_chars: int,
) -> tuple[str, str]:
    final_answer = ""
    thinking_log = ""
    for line in lines:
        final_answer_value = _extract_labeled_value(line, FINAL_ANSWER_LABELS)
        if final_answer_value is not None and not final_answer:
            final_answer = _truncate_text(final_answer_value, max_final_answer_chars)
            continue

        thinking_log_value = _extract_labeled_value(line, THINKING_LOG_LABELS)
        if thinking_log_value is not None and not thinking_log:
            thinking_log = _truncate_text(thinking_log_value, max_thinking_log_chars)

    return final_answer, thinking_log


def _resolve_reasoning_steps(
    lines: list[str],
    max_steps: int,
    max_step_chars: int,
) -> list[str]:
    reasoning_steps = _collect_steps_from_lines(
        lines,
        max_steps=max_steps,
        max_step_chars=max_step_chars,
    )
    if reasoning_steps:
        return reasoning_steps

    return [_truncate_text(FALLBACK_REASONING_STEP, max_step_chars)]


def parse_reasoning_response(
    raw_output: Any,
    reasoning_limits: ReasoningLimits | None = None,
) -> dict[str, Any]:
    limits = reasoning_limits or _resolve_reasoning_limits()
    (
        max_output_chars,
        max_steps,
        max_step_chars,
        max_final_answer_chars,
        max_thinking_log_chars,
    ) = limits

    safe_text = _normalize_raw_reasoning_output(raw_output, max_output_chars)

    if not safe_text:
        return _fallback_empty_reasoning_response(
            max_final_answer_chars=max_final_answer_chars,
            max_step_chars=max_step_chars,
            max_thinking_log_chars=max_thinking_log_chars,
        )

    attempted_direct_json_fast_path = (
        len(safe_text) >= 2
        and safe_text[0] == "{"
        and safe_text[-1] == "}"
    )
    if attempted_direct_json_fast_path:
        parsed_fast_path = _try_parse_json_candidate(safe_text)
        if isinstance(parsed_fast_path, dict):
            return parsed_fast_path

    parsed_structured = _parse_structured_reasoning_object(
        safe_text,
        skip_direct_json_parse=attempted_direct_json_fast_path,
    )
    if parsed_structured is not None:
        return parsed_structured

    lines = _split_non_empty_lines(safe_text)
    final_answer, thinking_log = _extract_reasoning_fields_from_lines(
        lines,
        max_final_answer_chars=max_final_answer_chars,
        max_thinking_log_chars=max_thinking_log_chars,
    )
    reasoning_steps = _resolve_reasoning_steps(
        lines,
        max_steps=max_steps,
        max_step_chars=max_step_chars,
    )

    if not final_answer:
        final_answer = _truncate_text(FALLBACK_FINAL_ANSWER, max_final_answer_chars)

    if not thinking_log:
        thinking_log = _truncate_text(FALLBACK_THINKING_LOG, max_thinking_log_chars)

    return {
        "final_answer": final_answer,
        "reasoning_steps": reasoning_steps,
        "thinking_log": thinking_log,
    }


class LlmReasoningService:
    def __init__(
        self,
        text_provider: TextGenerationProvider,
        base_system_prompt_provider: Callable[[], str] | None = None,
        reasoning_system_prompt_provider: Callable[[], str] | None = None,
    ):
        self.text_provider = text_provider
        self.base_system_prompt_provider = (
            base_system_prompt_provider or get_base_system_prompt
        )
        self.reasoning_system_prompt_provider = (
            reasoning_system_prompt_provider or get_reasoning_system_prompt
        )

    def generate(self, prompt: str) -> dict[str, Any]:
        normalized_prompt = _normalize_prompt(prompt)
        reasoning_limits = _resolve_reasoning_limits()
        effective_system_prompt = compose_system_prompt(
            self.base_system_prompt_provider(),
            self.reasoning_system_prompt_provider(),
        )
        generate_text_kwargs = {"prompt": normalized_prompt}
        if effective_system_prompt is not None:
            generate_text_kwargs["system_prompt"] = effective_system_prompt

        output_text = self.text_provider.generate_text(**generate_text_kwargs)
        parsed_output = parse_reasoning_response(
            output_text,
            reasoning_limits=reasoning_limits,
        )
        return validate_reasoning_response(
            parsed_output,
            reasoning_limits=reasoning_limits,
        )


def validate_reasoning_response(
    payload: Any,
    reasoning_limits: ReasoningLimits | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OpenAIServiceError("OpenAI reasoning response JSON must be an object.")

    limits = reasoning_limits or _resolve_reasoning_limits()
    (
        _max_output_chars,
        max_steps,
        max_step_chars,
        max_final_answer_chars,
        max_thinking_log_chars,
    ) = limits

    final_answer = _normalize_reasoning_text(
        payload.get("final_answer"),
        "final_answer",
        max_final_answer_chars,
    )
    thinking_log = _normalize_reasoning_text(
        payload.get("thinking_log"),
        "thinking_log",
        max_thinking_log_chars,
    )
    reasoning_steps_payload = payload.get("reasoning_steps")

    if isinstance(reasoning_steps_payload, str):
        reasoning_steps_payload = [reasoning_steps_payload]

    if not isinstance(reasoning_steps_payload, list) or not reasoning_steps_payload:
        raise OpenAIServiceError(
            "OpenAI reasoning response must include reasoning_steps as a non-empty array."
        )

    reasoning_steps: list[str] = []
    for step in reasoning_steps_payload[:max_steps]:
        normalized_step = _normalize_reasoning_text(
            step,
            "reasoning_steps",
            max_step_chars,
        )
        reasoning_steps.append(normalized_step)

    if not reasoning_steps:
        raise OpenAIServiceError(
            "OpenAI reasoning response must include reasoning_steps as a non-empty array."
        )

    return {
        "final_answer": final_answer,
        "reasoning_steps": reasoning_steps,
        "thinking_log": thinking_log,
    }
