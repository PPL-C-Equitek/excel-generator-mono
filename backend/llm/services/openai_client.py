import json
from typing import Any

from django.conf import settings
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)


class OpenAIServiceError(Exception):
    """Raised when the OpenAI integration cannot return a valid result."""


class OpenAIConfigurationError(OpenAIServiceError):
    """Raised when OpenAI settings are missing or invalid."""


class OpenAIUpstreamError(OpenAIServiceError):
    """Raised when upstream OpenAI call fails with a known HTTP-like status."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _build_client() -> OpenAI:
    api_key = settings.OPENAI_API_KEY.strip()
    if not api_key:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def _map_api_status_to_http(status_code: int | None) -> int:
    if status_code == 401:
        return 401
    if status_code == 429:
        return 429
    if status_code in (408, 504):
        return 504
    return 502


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

    try:
        response = client.responses.create(**request_payload)
    except AuthenticationError as exc:
        raise OpenAIUpstreamError("LLM authentication failed.", status_code=401) from exc
    except RateLimitError as exc:
        raise OpenAIUpstreamError("LLM rate limit exceeded.", status_code=429) from exc
    except APITimeoutError as exc:
        raise OpenAIUpstreamError("LLM request timed out.", status_code=504) from exc
    except APIStatusError as exc:
        status_code = _map_api_status_to_http(getattr(exc, "status_code", None))
        raise OpenAIUpstreamError("LLM provider request failed.", status_code=status_code) from exc
    except (APIConnectionError, APIError) as exc:
        raise OpenAIUpstreamError("LLM provider request failed.", status_code=502) from exc

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
    except json.JSONDecodeError as exc:
        raise OpenAIServiceError("OpenAI response is not valid JSON.") from exc

    if not isinstance(parsed_output, (dict, list)):
        raise OpenAIServiceError("OpenAI response JSON must be an object or array.")
    return parsed_output
