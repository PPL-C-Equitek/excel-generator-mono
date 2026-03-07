import json
from typing import Any

from django.conf import settings
from openai import OpenAI


class OpenAIServiceError(Exception):
    """Raised when the OpenAI integration cannot return a valid result."""


class OpenAIConfigurationError(OpenAIServiceError):
    """Raised when OpenAI settings are missing or invalid."""


def _build_client() -> OpenAI:
    api_key = settings.OPENAI_API_KEY.strip()
    if not api_key:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def generate_text(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt must be a non-empty string.")

    client = _build_client()
    request_payload = {
        "model": settings.OPENAI_MODEL,
        "input": prompt,
    }

    system_prompt = settings.OPENAI_SYSTEM_PROMPT.strip()
    if system_prompt:
        request_payload["instructions"] = system_prompt

    response = client.responses.create(**request_payload)
    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise OpenAIServiceError("OpenAI response did not include output_text.")
    return output_text


def generate_json(input_json: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    if not isinstance(input_json, (dict, list)):
        raise ValueError("input_json must be an object or array.")

    output_text = generate_text(prompt=json.dumps(input_json))
    try:
        parsed_output = json.loads(output_text)
    except json.JSONDecodeError:
        raise OpenAIServiceError("OpenAI response is not valid JSON.")

    if not isinstance(parsed_output, (dict, list)):
        raise OpenAIServiceError("OpenAI response JSON must be an object or array.")
    return parsed_output
