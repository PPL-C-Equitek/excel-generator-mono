from uuid import UUID

from rest_framework.response import Response

from ..repositories import get_thinking_log_queryset_for_user

INVALID_REQUEST_DETAIL = "Invalid request payload."
INVALID_THINKING_LOG_PAGINATION_DETAIL = "Invalid thinking log pagination request."
INVALID_THINKING_LOG_IDENTIFIER_DETAIL = "Invalid thinking log identifier."
THINKING_LOG_NOT_FOUND_DETAIL = "Thinking log not found."
MAX_THINKING_LOG_PAGE_SIZE = 100


def _thinking_log_not_found_response():
    return Response({"detail": THINKING_LOG_NOT_FOUND_DETAIL}, status=404)


def _invalid_thinking_log_pagination_response():
    return Response(
        {
            "detail": INVALID_REQUEST_DETAIL,
            "errors": {"pagination": [INVALID_THINKING_LOG_PAGINATION_DETAIL]},
        },
        status=400,
    )


def _invalid_thinking_log_identifier_response(field_name: str):
    return Response(
        {"detail": INVALID_REQUEST_DETAIL, "errors": {field_name: [INVALID_THINKING_LOG_IDENTIFIER_DETAIL]}},
        status=400,
    )


def _parse_thinking_log_positive_int(value, default, minimum=1):
    if value is None:
        return default

    parsed = int(value)
    if parsed < minimum:
        raise ValueError
    return parsed


def _parse_thinking_log_page_size(value, default=10):
    parsed = _parse_thinking_log_positive_int(value, default=default)
    if parsed > MAX_THINKING_LOG_PAGE_SIZE:
        raise ValueError
    return parsed


def _parse_thinking_log_identifier(value, field_name: str):
    normalized_value = value.strip() if isinstance(value, str) else ""
    if not normalized_value:
        return None

    try:
        return UUID(normalized_value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(field_name) from exc


def _build_thinking_log_queryset_for_user(user, session_id=None, chat_id=None, request_id=None):
    queryset = get_thinking_log_queryset_for_user(user)

    if session_id:
        queryset = queryset.filter(session_id=session_id)

    if chat_id:
        queryset = queryset.filter(source_message_id=chat_id)
    elif request_id:
        queryset = queryset.filter(id=request_id)

    return queryset.defer("export_output_json").order_by("-created_at", "-id")
