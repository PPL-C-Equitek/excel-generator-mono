import json
from typing import Any, Callable, Protocol

from django.conf import settings

from custom_schemas.models import CustomSchema

from .openai_client import OpenAIServiceError


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


def get_base_system_prompt() -> str:
    raw_prompt = getattr(settings, "OPENAI_SYSTEM_PROMPT", "")
    if not isinstance(raw_prompt, str):
        return ""
    return raw_prompt.strip()


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
