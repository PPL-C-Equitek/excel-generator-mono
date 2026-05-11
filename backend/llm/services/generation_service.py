import json
from typing import Any, Callable, Protocol

from custom_schemas.models import CustomSchema

from llm.prompts.extraction import build_extraction_prompt

from .openai_client import OpenAIServiceError
from .reasoning_service import TextGenerationProvider, compose_system_prompt, get_base_system_prompt


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
        refinement_instruction: str | None = None,
        chat_context: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        schema_prompt_fragment = None
        if custom_schema_id is not None:
            schema_prompt_fragment = self.schema_prompt_source.get_prompt_fragment(
                custom_schema_id
            )

        extraction_prompt = build_extraction_prompt(
            schema_hint=schema_prompt_fragment,
            refinement_instruction=refinement_instruction,
            chat_context=chat_context,
        )
        effective_system_prompt = compose_system_prompt(
            self.base_system_prompt_provider(),
            extraction_prompt,
        )
        return self.json_generator.generate(
            input_json=input_json,
            system_prompt=effective_system_prompt,
        )
