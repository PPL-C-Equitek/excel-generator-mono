from contextlib import contextmanager
import math
import json
from threading import Lock
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
_DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
_DEFAULT_OPENAI_MAX_RETRIES = 2
_DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS = 4000
_DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN = 512
_DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX = 4096
_DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO = 1.0


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
    def __init__(self):
        self._client: OpenAI | None = None
        self._client_signature: tuple[str, str, float, int] | None = None

    def _get_client(self) -> OpenAI:
        signature = _resolve_client_signature()
        if self._client is None or self._client_signature != signature:
            self._client = _build_client_from_signature(*signature)
            self._client_signature = signature
        return self._client

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        client = self._get_client()
        effective_system_prompt = _resolve_system_prompt(system_prompt)
        request_payload = {
            "model": settings.OPENAI_MODEL,
            "input": prompt,
        }
        request_payload.update(
            _build_response_generation_options(
                prompt=prompt,
                system_prompt=effective_system_prompt,
            )
        )
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


_TEXT_PROVIDER_SINGLETON: OpenAITextGenerationProvider | None = None
_TEXT_PROVIDER_LOCK = Lock()


def _resolve_system_prompt(system_prompt: str | None = None) -> str:
    raw_prompt = settings.OPENAI_SYSTEM_PROMPT if system_prompt is None else system_prompt
    if not isinstance(raw_prompt, str):
        return ""
    return raw_prompt.strip()


def _resolve_client_signature() -> tuple[str, str, float, int]:
    api_key_raw = getattr(settings, "OPENAI_API_KEY", "")
    api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else ""
    if not api_key:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured.")

    base_url = getattr(settings, "OPENAI_BASE_URL", "")
    normalized_base_url = base_url.strip() if isinstance(base_url, str) else ""
    timeout_seconds = _resolve_openai_timeout_seconds()
    max_retries = _resolve_openai_max_retries()
    return api_key, normalized_base_url, timeout_seconds, max_retries


def _build_client_from_signature(
    api_key: str,
    normalized_base_url: str,
    timeout_seconds: float,
    max_retries: int,
) -> OpenAI:
    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout_seconds,
        "max_retries": max_retries,
    }
    if normalized_base_url:
        client_kwargs["base_url"] = normalized_base_url
    return OpenAI(**client_kwargs)


def _build_client() -> OpenAI:
    signature = _resolve_client_signature()
    return _build_client_from_signature(*signature)


def _resolve_openai_timeout_seconds() -> float:
    raw_value = getattr(settings, "OPENAI_TIMEOUT_SECONDS", _DEFAULT_OPENAI_TIMEOUT_SECONDS)
    if isinstance(raw_value, bool):
        return _DEFAULT_OPENAI_TIMEOUT_SECONDS
    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
        if numeric_value > 0:
            return numeric_value
        return _DEFAULT_OPENAI_TIMEOUT_SECONDS
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return _DEFAULT_OPENAI_TIMEOUT_SECONDS
        try:
            numeric_value = float(stripped_value)
        except ValueError:
            return _DEFAULT_OPENAI_TIMEOUT_SECONDS
        if numeric_value > 0:
            return numeric_value
    return _DEFAULT_OPENAI_TIMEOUT_SECONDS


def _resolve_openai_max_retries() -> int:
    raw_value = getattr(settings, "OPENAI_MAX_RETRIES", _DEFAULT_OPENAI_MAX_RETRIES)
    if isinstance(raw_value, bool):
        return _DEFAULT_OPENAI_MAX_RETRIES
    if isinstance(raw_value, int):
        return raw_value if raw_value >= 0 else _DEFAULT_OPENAI_MAX_RETRIES
    if isinstance(raw_value, float):
        numeric_value = int(raw_value)
        return numeric_value if numeric_value >= 0 else _DEFAULT_OPENAI_MAX_RETRIES
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return _DEFAULT_OPENAI_MAX_RETRIES
        try:
            numeric_value = int(stripped_value)
        except ValueError:
            return _DEFAULT_OPENAI_MAX_RETRIES
        return numeric_value if numeric_value >= 0 else _DEFAULT_OPENAI_MAX_RETRIES
    return _DEFAULT_OPENAI_MAX_RETRIES


def _resolve_positive_int_setting(name: str, default: int) -> int:
    raw_value = getattr(settings, name, default)
    if isinstance(raw_value, bool):
        return default
    if isinstance(raw_value, int):
        return raw_value if raw_value > 0 else default
    if isinstance(raw_value, float):
        numeric_value = int(raw_value)
        return numeric_value if numeric_value > 0 else default
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return default
        try:
            numeric_value = int(stripped_value)
        except ValueError:
            return default
        return numeric_value if numeric_value > 0 else default
    return default


def _resolve_positive_float_setting(name: str, default: float) -> float:
    raw_value = getattr(settings, name, default)
    if isinstance(raw_value, bool):
        return default
    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
        return numeric_value if numeric_value > 0 else default
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return default
        try:
            numeric_value = float(stripped_value)
        except ValueError:
            return default
        return numeric_value if numeric_value > 0 else default
    return default


def _resolve_optional_openai_temperature() -> float | None:
    raw_value = getattr(settings, "OPENAI_TEMPERATURE", None)
    if raw_value in (None, "") or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        numeric_value = float(raw_value)
    elif isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return None
        try:
            numeric_value = float(stripped_value)
        except ValueError:
            return None
    else:
        return None

    if 0 <= numeric_value <= 2:
        return numeric_value
    return None


def _resolve_optional_openai_seed() -> int | None:
    raw_value = getattr(settings, "OPENAI_SEED", None)
    if raw_value in (None, "") or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return None
        try:
            return int(stripped_value)
        except ValueError:
            return None
    return None


def _resolve_optional_openai_max_output_tokens() -> int | None:
    raw_value = getattr(settings, "OPENAI_MAX_OUTPUT_TOKENS", None)
    if raw_value in (None, "") or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value if raw_value > 0 else None
    if isinstance(raw_value, float):
        numeric_value = int(raw_value)
        return numeric_value if numeric_value > 0 else None
    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return None
        try:
            numeric_value = int(stripped_value)
        except ValueError:
            return None
        return numeric_value if numeric_value > 0 else None
    return None


def _resolve_adaptive_max_output_tokens(prompt_context: str | None) -> int | None:
    if not isinstance(prompt_context, str):
        return None

    normalized_prompt_context = prompt_context.strip()
    if not normalized_prompt_context:
        return None

    threshold_chars = _resolve_positive_int_setting(
        "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS",
        _DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS,
    )
    if len(normalized_prompt_context) < threshold_chars:
        return None

    minimum_tokens = _resolve_positive_int_setting(
        "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN",
        _DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN,
    )
    maximum_tokens = _resolve_positive_int_setting(
        "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX",
        _DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX,
    )
    ratio = _resolve_positive_float_setting(
        "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
        _DEFAULT_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO,
    )

    if maximum_tokens < minimum_tokens:
        maximum_tokens = minimum_tokens

    estimated_prompt_tokens = max(1, math.ceil(len(normalized_prompt_context) / 4))
    adaptive_tokens = int(estimated_prompt_tokens * ratio)
    adaptive_tokens = max(minimum_tokens, adaptive_tokens)
    adaptive_tokens = min(maximum_tokens, adaptive_tokens)
    return adaptive_tokens


def _resolve_common_generation_options(
    prompt_context: str | None = None,
) -> tuple[float | None, int | None, int | None]:
    temperature = _resolve_optional_openai_temperature()
    seed = _resolve_optional_openai_seed()
    max_output_tokens = _resolve_optional_openai_max_output_tokens()
    if max_output_tokens is None:
        max_output_tokens = _resolve_adaptive_max_output_tokens(prompt_context)
    return temperature, seed, max_output_tokens


def _apply_generation_options(
    options: dict[str, Any],
    temperature: float | None,
    seed: int | None,
    max_output_tokens: int | None,
    *,
    token_key: str,
) -> dict[str, Any]:
    if temperature is not None:
        options["temperature"] = temperature
    if seed is not None:
        options["seed"] = seed
    if max_output_tokens is not None:
        options[token_key] = max_output_tokens
    return options


def _build_response_generation_options(
    prompt: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {}
    prompt_context = prompt
    if isinstance(system_prompt, str) and system_prompt.strip():
        prompt_context = f"{system_prompt.strip()}\n{prompt}"

    temperature, seed, max_output_tokens = _resolve_common_generation_options(
        prompt_context
    )
    return _apply_generation_options(
        options,
        temperature,
        seed,
        max_output_tokens,
        token_key="max_output_tokens",
    )


def _extract_message_content_for_budget(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        return json.dumps(content) if content is not None else ""
    if isinstance(message, str):
        return message
    return ""


def _build_prompt_context_from_messages(messages: list[dict]) -> str:
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = _extract_message_content_for_budget(message)
        if isinstance(role, str) and role.strip():
            parts.append(f"{role.strip()}: {content}")
        else:
            parts.append(content)
    return "\n".join(parts)


def _build_chat_generation_options(messages: list[dict]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    prompt_context = _build_prompt_context_from_messages(messages)
    temperature, seed, max_output_tokens = _resolve_common_generation_options(
        prompt_context
    )
    return _apply_generation_options(
        options,
        temperature,
        seed,
        max_output_tokens,
        token_key="max_completion_tokens",
    )


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
            **_build_chat_generation_options(messages),
        )

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError):
        content = None

    normalized_content = _normalize_chat_message_content(content)
    if not normalized_content:
        raise OpenAIServiceError("OpenAI response did not include output_text.")
    return normalized_content


def _normalize_chat_message_content(content: Any) -> str | None:
    if isinstance(content, str):
        normalized_content = content.strip()
        return normalized_content or None

    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text_candidate = item.get("text") or item.get("content")
            else:
                text_candidate = getattr(item, "text", None) or getattr(item, "content", None)

            if isinstance(text_candidate, str) and text_candidate.strip():
                chunks.append(text_candidate.strip())

        merged_content = "\n".join(chunks).strip()
        return merged_content or None

    return None


def _get_text_generation_provider() -> OpenAITextGenerationProvider:
    global _TEXT_PROVIDER_SINGLETON
    if _TEXT_PROVIDER_SINGLETON is not None:
        return _TEXT_PROVIDER_SINGLETON

    with _TEXT_PROVIDER_LOCK:
        if _TEXT_PROVIDER_SINGLETON is None:
            _TEXT_PROVIDER_SINGLETON = OpenAITextGenerationProvider()
        return _TEXT_PROVIDER_SINGLETON


def reset_text_generation_provider_cache() -> None:
    global _TEXT_PROVIDER_SINGLETON
    with _TEXT_PROVIDER_LOCK:
        _TEXT_PROVIDER_SINGLETON = None


def generate_text(prompt: str, system_prompt: str | None = None) -> str:
    provider = _get_text_generation_provider()
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
            **_build_chat_generation_options(messages),
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
            **_build_chat_generation_options(messages),
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
