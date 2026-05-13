from contextlib import contextmanager
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


_LLM_PROVIDER_FAILED = "LLM provider request failed."


class OpenAIServiceError(Exception):
    """Raised when the OpenAI integration cannot return a valid result."""


class OpenAIConfigurationError(OpenAIServiceError):
    """Raised when OpenAI settings are missing or invalid."""


class OpenAIUpstreamError(OpenAIServiceError):
    """Raised when upstream OpenAI call fails with a known HTTP-like status."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@contextmanager
def handle_openai_exceptions():
    try:
        yield
    except AuthenticationError as exc:
        raise OpenAIUpstreamError("LLM authentication failed.", status_code=502) from exc
    except RateLimitError as exc:
        raise OpenAIUpstreamError("LLM rate limit exceeded.", status_code=429) from exc
    except APITimeoutError as exc:
        raise OpenAIUpstreamError("LLM request timed out.", status_code=504) from exc
    except APIStatusError as exc:
        status_code = _map_api_status_to_http(getattr(exc, "status_code", None))
        raise OpenAIUpstreamError(_LLM_PROVIDER_FAILED, status_code=status_code) from exc
    except (APIConnectionError, APIError) as exc:
        raise OpenAIUpstreamError(_LLM_PROVIDER_FAILED, status_code=502) from exc


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
            with handle_openai_exceptions():
                response = client.responses.create(**request_payload)
        except OpenAIUpstreamError as exc:
            if exc.status_code != 404:
                raise
            # Fallback for OpenAI-compatible providers that do not implement /responses.
            return _generate_text_via_chat_completions(
                client=client,
                prompt=prompt,
                system_prompt=effective_system_prompt or None,
            )

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

    base_url = getattr(settings, "OPENAI_BASE_URL", "")
    normalized_base_url = base_url.strip() if isinstance(base_url, str) else ""
    if normalized_base_url:
        return OpenAI(api_key=api_key, base_url=normalized_base_url)
    return OpenAI(api_key=api_key)


def _map_api_status_to_http(status_code: int | None) -> int:
    if status_code == 404:
        return 404
    if status_code == 429:
        return 429
    if status_code in (408, 504):
        return 504
    return 502


def _generate_text_via_chat_completions(
    client: OpenAI,
    prompt: str,
    system_prompt: str | None = None,
) -> str:
    messages: list[dict[str, str]] = []
    if isinstance(system_prompt, str) and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt})

    with handle_openai_exceptions():
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
        )

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError):
        content = None

    normalized_content = _normalize_chat_message_content(content)
    if not normalized_content:
        raise OpenAIServiceError("OpenAI response did not include output_text.")
    return normalized_content


def _extract_text_from_content_item(item: Any) -> str | None:
    if isinstance(item, dict):
        candidate = item.get("text") or item.get("content")
    else:
        candidate = getattr(item, "text", None) or getattr(item, "content", None)
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return None


def _normalize_chat_message_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        chunks = [t for item in content if (t := _extract_text_from_content_item(item))]
        return "\n".join(chunks).strip() or None
    return None


def generate_text(prompt: str, system_prompt: str | None = None) -> str:
    provider = OpenAITextGenerationProvider()
    return provider.generate_text(prompt=prompt, system_prompt=system_prompt)


def generate_streaming_chat_response(messages: list[dict]):
    """Generator that yields text chunks from OpenAI with stream=True."""
    if not messages:
        raise ValueError("messages must be a non-empty list.")

    client = _build_client()

    with handle_openai_exceptions():
        stream = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            stream=True,
        )

    try:
        with handle_openai_exceptions():
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except (AttributeError, IndexError):
                    delta = None
                if delta:
                    yield delta
    finally:
        stream.close()


def generate_chat_response(messages: list[dict]) -> str:
    if not messages:
        raise ValueError("messages must be a non-empty list.")

    client = _build_client()

    with handle_openai_exceptions():
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
        )

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError):
        content = None

    normalized_content = _normalize_chat_message_content(content)
    if not normalized_content:
        raise OpenAIServiceError("OpenAI response did not include a reply.")
    return normalized_content


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
