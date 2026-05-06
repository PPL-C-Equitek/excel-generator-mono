"""Use-case level facade for session operations.

Step 1 scope:
- Introduce a facade entry point.
- Keep behavior unchanged by delegating to `chat_sessions.services`.
"""

from __future__ import annotations

from typing import Any

from . import services


class SessionFacade:
    """Facade API for chat session use cases."""

    def __init__(self, service_module: Any = services) -> None:
        self._services = service_module

    def build_frontend_thinking_log_response(self, payload: Any) -> dict[str, Any]:
        return self._services.build_frontend_thinking_log_response(payload)

    def create_session_for_user(self, owner: Any, title: str = "") -> Any:
        return self._services.create_session_for_user(owner, title=title)

    def list_sessions_for_user(
        self,
        user: Any,
        limit: int | None = None,
        offset: int = 0,
    ) -> Any:
        return self._services.list_sessions_for_user(user, limit=limit, offset=offset)

    def get_session_for_user(self, user: Any, session_id: Any) -> Any:
        return self._services.get_session_for_user(user, session_id)

    def get_generated_output_for_session_user(
        self,
        user: Any,
        session_id: Any,
        output_id: Any,
    ) -> Any:
        return self._services.get_generated_output_for_session_user(
            user,
            session_id,
            output_id,
        )

    def get_generated_output_for_user(self, user: Any, output_id: Any) -> Any:
        return self._services.get_generated_output_for_user(user, output_id)

    def get_chat_message_for_user(self, user: Any, message_id: Any) -> Any:
        return self._services.get_chat_message_for_user(user, message_id)

    def get_paginated_session_detail_for_user(
        self,
        user: Any,
        session_id: Any,
        messages_limit: int = services.SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
        messages_offset: int = 0,
        outputs_limit: int = services.SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
        outputs_offset: int = 0,
    ) -> Any:
        return self._services.get_paginated_session_detail_for_user(
            user,
            session_id,
            messages_limit=messages_limit,
            messages_offset=messages_offset,
            outputs_limit=outputs_limit,
            outputs_offset=outputs_offset,
        )

    def build_resume_context_for_user(self, user: Any, session_id: Any) -> Any:
        return self._services.build_resume_context_for_user(user, session_id)

    def get_default_session_detail_pagination(self) -> dict[str, int]:
        return self._services.get_default_session_detail_pagination()

    def validate_session_detail_pagination_params(
        self,
        pagination: dict[str, int],
    ) -> None:
        self._services.validate_session_detail_pagination_params(pagination)

    def update_session_title(self, session: Any, title: str) -> Any:
        return self._services.update_session_title(session, title)

    def sanitize_session_title(self, title: str) -> str:
        return self._services.sanitize_session_title(title)

    def resolve_session_title(
        self,
        candidate_title: str,
        fallback: str = "New Chat",
    ) -> str:
        return self._services.resolve_session_title(
            candidate_title,
            fallback=fallback,
        )

    def generate_session_title_from_message(
        self,
        message: str,
        fallback: str = "New Chat",
    ) -> str:
        return self._services.generate_session_title_from_message(
            message,
            fallback=fallback,
        )

    def delete_session(self, session: Any) -> None:
        self._services.delete_session(session)

    def append_user_message(
        self,
        session: Any,
        content: str,
        target_output: Any = None,
    ) -> Any:
        return self._services.append_user_message(
            session,
            content,
            target_output=target_output,
        )

    def append_assistant_message(
        self,
        session: Any,
        content: str,
        thinking_log: str | None = None,
    ) -> Any:
        return self._services.append_assistant_message(
            session,
            content,
            thinking_log=thinking_log,
        )

    def create_generated_output(
        self,
        session: Any,
        output_json: Any,
        thinking_log: str = "",
        export_output_json: dict[str, Any] | None = None,
        reasoning: dict[str, Any] | None = None,
        source_message: Any = None,
        parent_output: Any = None,
    ) -> Any:
        return self._services.create_generated_output(
            session,
            output_json,
            thinking_log=thinking_log,
            export_output_json=export_output_json,
            reasoning=reasoning,
            source_message=source_message,
            parent_output=parent_output,
        )

    def build_history_with_summary(
        self,
        session: Any,
        full_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return self._services.build_history_with_summary(session, full_history)


def create_session_facade() -> SessionFacade:
    return SessionFacade()


default_session_facade = create_session_facade()

