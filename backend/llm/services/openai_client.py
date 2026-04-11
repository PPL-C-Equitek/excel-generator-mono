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


class OpenAITextGenerationProvider:
    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        client = _build_client()
        request_payload = {
            "model": settings.OPENAI_MODEL,
            "input": prompt,
        }

        effective_system_prompt = _resolve_system_prompt(system_prompt)
        if effective_system_prompt:
            request_payload["instructions"] = effective_system_prompt

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


def _resolve_system_prompt(system_prompt: str | None = None) -> str:
    raw_prompt = settings.OPENAI_SYSTEM_PROMPT if system_prompt is None else system_prompt
    if not isinstance(raw_prompt, str):
        return ""
    return raw_prompt.strip()


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


def generate_text(prompt: str, system_prompt: str | None = None) -> str:
    provider = OpenAITextGenerationProvider()
    return provider.generate_text(prompt=prompt, system_prompt=system_prompt)


def generate_json(
    input_json: dict[str, Any] | list[Any],
    system_prompt: str | None = None,
) -> dict[str, Any] | list[Any]:
    from .generation_service import JsonGenerationService

    class _FunctionTextGenerationProvider:
        def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
            return generate_text(prompt=prompt, system_prompt=system_prompt)

    service = JsonGenerationService(text_provider=_FunctionTextGenerationProvider())
    return service.generate(input_json=input_json, system_prompt=system_prompt)
