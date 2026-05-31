import json
from typing import Any, Callable, Protocol

from custom_schemas.models import CustomSchema

from llm.prompts.extraction import build_extraction_prompt

from .openai_client import OpenAIServiceError
from .reasoning_service import TextGenerationProvider, compose_system_prompt, get_base_system_prompt
from .settings_resolvers import (
    resolve_positive_int_setting as _resolve_positive_int_setting,
)


_UPLOAD_PROMPT_NOISE_KEYS = {"status", "message", "size"}
_DEFAULT_PROMPT_MAX_CHARS = 24_000
_DEFAULT_PROMPT_MAX_TABLES = 12
_DEFAULT_PROMPT_MAX_ROWS_PER_TABLE = 60
_DEFAULT_PROMPT_MAX_COLUMNS_PER_ROW = 20
_DEFAULT_PROMPT_MAX_CELL_CHARS = 160


def _truncate_text_cell(value: Any, max_chars: int) -> Any:
    if not isinstance(value, str):
        return value

    normalized = value.strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars]}..."


def _truncate_table_rows(
    rows: Any,
    max_rows: int,
    max_columns: int,
    max_cell_chars: int,
) -> Any:
    if not isinstance(rows, list):
        return rows

    truncated_rows = []
    for row in rows[:max_rows]:
        if isinstance(row, list):
            truncated_rows.append(
                [
                    _truncate_text_cell(cell, max_cell_chars)
                    for cell in row[:max_columns]
                ]
            )
            continue

        if isinstance(row, dict):
            truncated_row: dict[str, Any] = {}
            for index, (key, value) in enumerate(row.items()):
                if index >= max_columns:
                    break
                truncated_row[key] = _truncate_text_cell(value, max_cell_chars)
            truncated_rows.append(truncated_row)
            continue

        truncated_rows.append(_truncate_text_cell(row, max_cell_chars))

    return truncated_rows


def _apply_extracted_payload_budget(
    extracted_payload: Any,
    max_tables: int,
    max_rows: int,
    max_columns: int,
    max_cell_chars: int,
) -> Any:
    if not isinstance(extracted_payload, dict):
        return extracted_payload

    budgeted: dict[str, Any] = {}
    for index, (table_name, rows) in enumerate(extracted_payload.items()):
        if index >= max_tables:
            break
        budgeted[table_name] = _truncate_table_rows(
            rows=rows,
            max_rows=max_rows,
            max_columns=max_columns,
            max_cell_chars=max_cell_chars,
        )
    return budgeted


def _build_prompt_budget_summary(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {
            "_prompt_budget": {
                "applied": True,
                "mode": "summary",
                "list_items": len(payload),
            }
        }

    summary_payload: dict[str, Any] = {
        "_prompt_budget": {
            "applied": True,
            "mode": "summary",
        }
    }
    filename = payload.get("filename")
    format_value = payload.get("format")
    user_prompt = payload.get("user_prompt")
    extracted = payload.get("extracted")
    if isinstance(filename, str) and filename.strip():
        summary_payload["filename"] = filename.strip()
    if isinstance(format_value, str) and format_value.strip():
        summary_payload["format"] = format_value.strip()
    if isinstance(user_prompt, str) and user_prompt.strip():
        summary_payload["user_prompt"] = user_prompt.strip()[:300]
    if isinstance(extracted, dict):
        summary_payload["extracted_summary"] = {
            "table_count": len(extracted),
            "table_names": list(extracted.keys())[:10],
        }
    return summary_payload


def _apply_prompt_payload_budget(
    payload: dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any]:
    max_prompt_chars = _resolve_positive_int_setting(
        "LLM_PROMPT_MAX_CHARS",
        _DEFAULT_PROMPT_MAX_CHARS,
    )
    prompt_text = json.dumps(payload)
    if len(prompt_text) <= max_prompt_chars:
        return payload

    max_tables = _resolve_positive_int_setting(
        "LLM_PROMPT_MAX_TABLES",
        _DEFAULT_PROMPT_MAX_TABLES,
    )
    max_rows = _resolve_positive_int_setting(
        "LLM_PROMPT_MAX_ROWS_PER_TABLE",
        _DEFAULT_PROMPT_MAX_ROWS_PER_TABLE,
    )
    max_columns = _resolve_positive_int_setting(
        "LLM_PROMPT_MAX_COLUMNS_PER_ROW",
        _DEFAULT_PROMPT_MAX_COLUMNS_PER_ROW,
    )
    max_cell_chars = _resolve_positive_int_setting(
        "LLM_PROMPT_MAX_CELL_CHARS",
        _DEFAULT_PROMPT_MAX_CELL_CHARS,
    )

    budgeted_payload = payload
    if isinstance(payload, dict):
        budgeted_payload = dict(payload)
        extracted_payload = budgeted_payload.get("extracted")
        if extracted_payload is not None:
            budgeted_payload["extracted"] = _apply_extracted_payload_budget(
                extracted_payload=extracted_payload,
                max_tables=max_tables,
                max_rows=max_rows,
                max_columns=max_columns,
                max_cell_chars=max_cell_chars,
            )

        original_input_payload = budgeted_payload.get("original_input_json")
        if isinstance(original_input_payload, (dict, list)):
            budgeted_payload["original_input_json"] = _apply_prompt_payload_budget(
                original_input_payload
            )

        budget_metadata = {
            "applied": True,
            "mode": "sampled",
            "max_prompt_chars": max_prompt_chars,
            "max_tables": max_tables,
            "max_rows_per_table": max_rows,
            "max_columns_per_row": max_columns,
            "max_cell_chars": max_cell_chars,
        }
        budgeted_payload["_prompt_budget"] = budget_metadata

    budgeted_text = json.dumps(budgeted_payload)
    if len(budgeted_text) <= max_prompt_chars:
        return budgeted_payload

    summary_payload = _build_prompt_budget_summary(budgeted_payload)
    summary_text = json.dumps(summary_payload)
    if len(summary_text) <= max_prompt_chars:
        return summary_payload

    trimmed_prompt = summary_payload.get("user_prompt")
    if isinstance(trimmed_prompt, str):
        summary_payload["user_prompt"] = trimmed_prompt[: max(1, max_prompt_chars // 6)]
    return summary_payload


def _extract_ocr_context(payload: dict[str, Any] | list[Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    direct_metadata = payload.get("ocr_metadata")
    if isinstance(direct_metadata, dict) and direct_metadata:
        return direct_metadata

    for nested_key in ("original_input_json", "input_json", "payload"):
        nested_payload = payload.get(nested_key)
        if isinstance(nested_payload, (dict, list)):
            nested_metadata = _extract_ocr_context(nested_payload)
            if nested_metadata:
                return nested_metadata

    extracted = payload.get("extracted")
    if isinstance(extracted, dict):
        nested_metadata = _extract_ocr_context(extracted)
        if nested_metadata:
            return nested_metadata

    return None


def _normalize_user_prompt(payload: dict[str, Any]) -> None:
    user_prompt = payload.get("user_prompt")
    if not isinstance(user_prompt, str):
        return

    trimmed_user_prompt = user_prompt.strip()
    if trimmed_user_prompt:
        payload["user_prompt"] = trimmed_user_prompt
        return

    payload.pop("user_prompt", None)


def _compact_input_json_for_prompt(
    input_json: dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any]:
    if not isinstance(input_json, dict):
        return input_json

    # Refinement wrapper payload keeps the same keys, but compacts nested upload input.
    if {
        "original_input_json",
        "previous_output_json",
        "validation_log",
    }.issubset(input_json.keys()):
        compact_payload = dict(input_json)
        original_input = compact_payload.get("original_input_json")
        if isinstance(original_input, (dict, list)):
            compact_payload["original_input_json"] = _compact_input_json_for_prompt(
                original_input
            )
        return compact_payload

    # Upload API wraps extracted data with transport metadata.
    # Keep semantic payload for LLM prompt and drop known wrapper noise.
    if "extracted" not in input_json:
        return input_json

    compact_payload = {
        key: value
        for key, value in input_json.items()
        if key not in _UPLOAD_PROMPT_NOISE_KEYS
    }
    _normalize_user_prompt(compact_payload)
    return compact_payload


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

        compact_prompt_payload = _compact_input_json_for_prompt(input_json)
        budgeted_prompt_payload = _apply_prompt_payload_budget(compact_prompt_payload)
        generate_text_kwargs = {"prompt": json.dumps(budgeted_prompt_payload)}
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
        self._schema_prompt_fragment_cache: dict[object, str] = {}

    def _get_schema_prompt_fragment(self, custom_schema_id) -> str:
        if custom_schema_id not in self._schema_prompt_fragment_cache:
            self._schema_prompt_fragment_cache[custom_schema_id] = (
                self.schema_prompt_source.get_prompt_fragment(custom_schema_id)
            )
        return self._schema_prompt_fragment_cache[custom_schema_id]

    def generate(
        self,
        input_json: dict[str, Any] | list[Any],
        custom_schema_id=None,
        refinement_instruction: str | None = None,
        chat_context: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        schema_prompt_fragment = None
        if custom_schema_id is not None:
            schema_prompt_fragment = self._get_schema_prompt_fragment(custom_schema_id)

        extraction_prompt = build_extraction_prompt(
            schema_hint=schema_prompt_fragment,
            refinement_instruction=refinement_instruction,
            chat_context=chat_context,
            ocr_context=_extract_ocr_context(input_json),
        )
        effective_system_prompt = compose_system_prompt(
            self.base_system_prompt_provider(),
            extraction_prompt,
        )
        return self.json_generator.generate(
            input_json=input_json,
            system_prompt=effective_system_prompt,
        )
