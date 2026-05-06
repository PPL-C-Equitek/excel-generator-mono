"""Title sanitization and generation operations for chat sessions."""

from __future__ import annotations

import re
from typing import Any, Callable

from llm.services.openai_client import generate_chat_response as _default_title_generator


def sanitize_session_title(title: Any) -> str:
    if not title:
        return ""

    stripped = str(title).strip()
    if not stripped:
        return ""

    normalized = re.sub(r"[\r\n\t]", " ", stripped)

    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {'"', "'"}
    ):
        normalized = normalized[1:-1].strip()

    return normalized[:120]


def resolve_session_title(candidate_title: Any, fallback: str = "New Chat") -> str:
    sanitized = sanitize_session_title(candidate_title)
    if not sanitized:
        return fallback
    return sanitized


def generate_session_title_from_message(
    message: str,
    fallback: str = "New Chat",
    title_generator: Callable[[list[dict[str, str]]], Any] | None = None,
) -> str:
    if not message or not message.strip():
        return fallback

    title_prompt = (
        "Berikan judul singkat maksimal 3-5 kata untuk chat berikut. "
        "Abaikan sapaan, ambil konteks utama. Jangan gunakan karakter newline, "
        f"cukup 1 kalimat: {message}"
    )

    generator = title_generator or _default_title_generator
    try:
        title_suggestion = generator([{"role": "user", "content": title_prompt}])
    except Exception:
        return fallback

    return resolve_session_title(title_suggestion, fallback=fallback)

