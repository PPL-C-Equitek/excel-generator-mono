import json
import re
from typing import Any, Callable, Protocol

from django.conf import settings

from custom_schemas.models import CustomSchema

from .openai_client import OpenAIServiceError


DEFAULT_REASONING_OUTPUT_TEXT_MAX_CHARS = 120000
DEFAULT_REASONING_FINAL_ANSWER_MAX_CHARS = 4000
DEFAULT_REASONING_THINKING_LOG_MAX_CHARS = 16000
DEFAULT_REASONING_STEP_MAX_CHARS = 2000
DEFAULT_REASONING_STEPS_MAX_ITEMS = 20

FALLBACK_FINAL_ANSWER = "Unable to parse final answer from model output."
FALLBACK_REASONING_STEP = "Unable to parse structured reasoning steps from model output."

STEP_LINE_PATTERN = re.compile(
    r"^(?:step\s*\d+\s*[:.\-)]+\s*|\d+\s*[.)-]\s*|[-*•]\s+)(.+)$",
    re.IGNORECASE,
)
FINAL_ANSWER_PATTERN = re.compile(
    r"^(?:final\s*answer|answer|conclusion)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
THINKING_LOG_PATTERN = re.compile(
    r"^(?:thinking\s*log|thinking|reasoning|analysis|thought\s*process)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
STEP_SECTION_PATTERN = re.compile(
    r"^(?:reasoning\s*steps?|steps?|analysis)\s*[:\-]?\s*$",
    re.IGNORECASE,
)


class TextGenerationProvider(Protocol):
    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str: ...


class JsonGenerationPort(Protocol):
    def generate(
        self,
        input_json: dict[str, Any] | list[Any],
        system_prompt: str | None = None,
    ) -> dict[str, Any] | list[Any]: ...


class CustomSchemaPromptSource(Protocol):
    def get_prompt_fragment(self, schema_id) -> str: ...


class CustomSchemaNotFoundError(Exception):
    """Raised when a requested custom schema cannot be found."""


class JsonGenerationService:
    def __init__(self, text_provider: TextGenerationProvider):
        self.text_provider = text_provider

    def generate(
        self,
        input_json: dict[str, Any] | list[Any],
        system_prompt: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        if not isinstance(input_json, (dict, list)):
            raise ValueError("input_json must be an object or array.")

        generate_text_kwargs = {"prompt": json.dumps(input_json)}
        if system_prompt is not None:
            generate_text_kwargs["system_prompt"] = system_prompt

        output_text = self.text_provider.generate_text(**generate_text_kwargs)
        try:
            parsed_output = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise OpenAIServiceError("OpenAI response is not valid JSON.") from exc

        if not isinstance(parsed_output, (dict, list)):
            raise OpenAIServiceError("OpenAI response JSON must be an object or array.")

        return parsed_output


class DjangoCustomSchemaPromptSource:
    def __init__(self, owner_id: object | None = None):
        self.owner_id = owner_id

    def get_prompt_fragment(self, schema_id) -> str:
        if self.owner_id is None:
            raise CustomSchemaNotFoundError("Custom schema not found.")

        try:
            schema = CustomSchema.objects.get(pk=schema_id, owner_id=self.owner_id)
        except CustomSchema.DoesNotExist as exc:
            raise CustomSchemaNotFoundError("Custom schema not found.") from exc

        return schema.prompt_fragment


class LlmGenerationService:
    def __init__(
        self,
        json_generator: JsonGenerationPort,
        schema_prompt_source: CustomSchemaPromptSource,
        base_system_prompt_provider: Callable[[], str] | None = None,
    ):
        self.json_generator = json_generator
        self.schema_prompt_source = schema_prompt_source
        self.base_system_prompt_provider = (
            base_system_prompt_provider or get_base_system_prompt
        )

    def generate(
        self,
        input_json: dict[str, Any] | list[Any],
        custom_schema_id=None,
    ) -> dict[str, Any] | list[Any]:
        schema_prompt_fragment = None
        if custom_schema_id is not None:
            schema_prompt_fragment = self.schema_prompt_source.get_prompt_fragment(
                custom_schema_id
            )

        effective_system_prompt = compose_system_prompt(
            self.base_system_prompt_provider(),
            schema_prompt_fragment,
        )
        return self.json_generator.generate(
            input_json=input_json,
            system_prompt=effective_system_prompt,
        )


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
        effective_system_prompt = compose_system_prompt(
            self.base_system_prompt_provider(),
            self.reasoning_system_prompt_provider(),
        )
        generate_text_kwargs = {"prompt": normalized_prompt}
        if effective_system_prompt is not None:
            generate_text_kwargs["system_prompt"] = effective_system_prompt

        output_text = self.text_provider.generate_text(**generate_text_kwargs)
        parsed_output = parse_reasoning_response(output_text)
        return validate_reasoning_response(parsed_output)


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
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _extract_json_from_fenced_blocks(text: str) -> list[str]:
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    return [candidate.strip() for candidate in matches if candidate.strip()]


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


def _collect_steps_from_lines(lines: list[str], max_steps: int, max_step_chars: int) -> list[str]:
    steps: list[str] = []
    inside_step_section = False

    for line in lines:
        if STEP_SECTION_PATTERN.match(line):
            inside_step_section = True
            continue

        step_match = STEP_LINE_PATTERN.match(line)
        if step_match:
            step = _truncate_text(step_match.group(1).strip(), max_step_chars)
            if step:
                steps.append(step)
            if len(steps) >= max_steps:
                break
            continue

        if inside_step_section and line:
            if FINAL_ANSWER_PATTERN.match(line) or THINKING_LOG_PATTERN.match(line):
                inside_step_section = False
                continue

            step = _truncate_text(line, max_step_chars)
            if step:
                steps.append(step)
            if len(steps) >= max_steps:
                break

    return steps


def _fallback_narrative_steps(text: str, max_steps: int, max_step_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
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


def parse_reasoning_response(raw_output: Any) -> dict[str, Any]:
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

    if isinstance(raw_output, str):
        safe_text = _truncate_text(raw_output.strip(), max_output_chars)
    else:
        safe_text = _truncate_text(str(raw_output or "").strip(), max_output_chars)

    if not safe_text:
        return {
            "final_answer": _truncate_text(FALLBACK_FINAL_ANSWER, max_final_answer_chars),
            "reasoning_steps": [_truncate_text(FALLBACK_REASONING_STEP, max_step_chars)],
            "thinking_log": _truncate_text(FALLBACK_FINAL_ANSWER, max_thinking_log_chars),
        }

    direct_json = _try_parse_json_candidate(safe_text)
    if isinstance(direct_json, dict):
        return direct_json

    for candidate in _extract_json_from_fenced_blocks(safe_text):
        parsed_candidate = _try_parse_json_candidate(candidate)
        if isinstance(parsed_candidate, dict):
            return parsed_candidate

    braced_candidate = _extract_braced_json_candidate(safe_text)
    if braced_candidate is not None:
        parsed_candidate = _try_parse_json_candidate(braced_candidate)
        if isinstance(parsed_candidate, dict):
            return parsed_candidate

    lines = _split_non_empty_lines(safe_text)
    final_answer = ""
    thinking_log = ""
    for line in lines:
        final_match = FINAL_ANSWER_PATTERN.match(line)
        if final_match and not final_answer:
            final_answer = _truncate_text(final_match.group(1).strip(), max_final_answer_chars)
            continue

        thinking_match = THINKING_LOG_PATTERN.match(line)
        if thinking_match and not thinking_log:
            thinking_log = _truncate_text(thinking_match.group(1).strip(), max_thinking_log_chars)
            continue

    reasoning_steps = _collect_steps_from_lines(
        lines,
        max_steps=max_steps,
        max_step_chars=max_step_chars,
    )
    if not reasoning_steps:
        reasoning_steps = _fallback_narrative_steps(
            safe_text,
            max_steps=max_steps,
            max_step_chars=max_step_chars,
        )

    if not reasoning_steps:
        reasoning_steps = [_truncate_text(FALLBACK_REASONING_STEP, max_step_chars)]

    if not final_answer:
        final_answer = _truncate_text(reasoning_steps[-1], max_final_answer_chars)

    if not thinking_log:
        thinking_log = _truncate_text(safe_text, max_thinking_log_chars)

    return {
        "final_answer": final_answer,
        "reasoning_steps": reasoning_steps,
        "thinking_log": thinking_log,
    }


def validate_reasoning_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OpenAIServiceError("OpenAI reasoning response JSON must be an object.")

    max_final_answer_chars = _get_positive_int_setting(
        "LLM_REASONING_FINAL_ANSWER_MAX_CHARS",
        DEFAULT_REASONING_FINAL_ANSWER_MAX_CHARS,
    )
    max_thinking_log_chars = _get_positive_int_setting(
        "LLM_REASONING_THINKING_LOG_MAX_CHARS",
        DEFAULT_REASONING_THINKING_LOG_MAX_CHARS,
    )
    max_steps = _get_positive_int_setting(
        "LLM_REASONING_STEPS_MAX_ITEMS",
        DEFAULT_REASONING_STEPS_MAX_ITEMS,
    )
    max_step_chars = _get_positive_int_setting(
        "LLM_REASONING_STEP_MAX_CHARS",
        DEFAULT_REASONING_STEP_MAX_CHARS,
    )

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
