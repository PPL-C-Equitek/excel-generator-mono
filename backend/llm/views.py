import json
import logging
from typing import Any, cast
from uuid import UUID

from chat_sessions.models import GeneratedOutput
from artifact_history.services import create_artifact_history
from django.db import transaction
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat_sessions.services import (
    append_assistant_message,
    append_user_message,
    build_history_with_summary,
    create_generated_output,
    create_session_for_user,
    generate_session_title_from_message,
    get_session_for_user,
    resolve_session_title,
    sanitize_session_title,
)
from authentication.permissions import IsVerifiedUser
from .serializers import (
    LlmGenerateRequestSerializer,
    LlmGenerateResponseSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer,
    LlmReasoningRequestSerializer,
    LlmReasoningResponseSerializer,
    ThinkingLogItemSerializer,
)
from .services.generation_service import (
    CustomSchemaNotFoundError,
    DjangoCustomSchemaPromptSource,
    JsonGenerationService,
    LlmGenerationService,
)
from .services.reasoning_service import (
    LlmReasoningService,
    generate_conversion_reasoning_response,
    generate_reasoning_response,
)
from .services.openai_client import (
    OpenAITextGenerationProvider,
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
    generate_chat_response,
)

logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"

INVALID_REQUEST_DETAIL = "Invalid request payload."
UNSUPPORTED_MEDIA_TYPE_DETAIL = "Content-Type must be application/json."
SERVICE_UNAVAILABLE_DETAIL = "Service unavailable. Please try again later."
UPSTREAM_FAILURE_DETAIL = "Failed to generate response from LLM provider."
INTERNAL_FAILURE_DETAIL = "Internal server error."
INVALID_INPUT_JSON_DETAIL = "Invalid input_json payload."
INVALID_PROMPT_DETAIL = "Invalid prompt payload."
CUSTOM_SCHEMA_NOT_FOUND_DETAIL = "Custom schema not found."
REASONING_META_KEYS = {"final_answer", "reasoning_steps", "thinking_log"}
SESSION_NOT_FOUND_DETAIL = "Session not found."
THINKING_LOG_NOT_FOUND_DETAIL = "Thinking log not found."
INVALID_THINKING_LOG_PAGINATION_DETAIL = "Invalid thinking log pagination request."
INVALID_THINKING_LOG_IDENTIFIER_DETAIL = "Invalid thinking log identifier."
MAX_THINKING_LOG_PAGE_SIZE = 100


def get_authenticated_user_id(user) -> object | None:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "id", None)


def build_llm_generation_service(user=None) -> LlmGenerationService:
    return LlmGenerationService(
        json_generator=JsonGenerationService(
            text_provider=OpenAITextGenerationProvider()
        ),
        schema_prompt_source=DjangoCustomSchemaPromptSource(
            owner_id=get_authenticated_user_id(user)
        ),
    )


def build_llm_reasoning_service() -> LlmReasoningService:
    return LlmReasoningService(text_provider=OpenAITextGenerationProvider())


def _normalize_filename_candidate(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_document_info_filename(payload):
    if not isinstance(payload, dict):
        return None

    document_info = payload.get("document_info")
    if not isinstance(document_info, dict):
        return None

    return _normalize_filename_candidate(document_info.get("filename"))


def extract_original_name(input_json, output_json) -> str:
    if isinstance(input_json, dict):
        input_filename = _normalize_filename_candidate(input_json.get("filename"))
        if input_filename:
            return input_filename

    return (
        _extract_document_info_filename(input_json)
        or _extract_document_info_filename(output_json)
        or "generated-output"
    )


def _extract_document_type(payload) -> str:
    if not isinstance(payload, dict):
        return "unknown"

    document_info = payload.get("document_info")
    if isinstance(document_info, dict):
        for key in ("source_type", "document_type", "file_type", "format"):
            value = document_info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    for key in ("document_type", "file_type", "format"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    return "unknown"


def _format_export_source_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"pdf"}:
        return "PDF"
    if normalized in {"excel", "xlsx", "xls"}:
        return "Excel"
    return ""


def _resolve_export_source_type(input_json, output_json) -> str:
    source_type = _format_export_source_type(_extract_document_type(input_json))
    if source_type:
        return source_type

    filename = extract_original_name(input_json, output_json).lower()
    if filename.endswith(".pdf"):
        return "PDF"

    return "Excel"


def _build_session_message_history(session):
    return [
        {"role": msg.role, "content": msg.content}
        for msg in session.messages.order_by("created_at")
    ]


def _build_new_session_title_prompt(history, message):
    return history[:-1] + [
        {
            "role": "user",
            "content": (
                f"{message}\n\n"
                "Reply to the message normally. "
                "Also generate a short 3-5 word session title. "
                'Return a valid JSON object with exactly two keys: "reply" and "title". '
                "Do NOT wrap the output in markdown."
            ),
        }
    ]


def _parse_send_message_json_result(raw_result):
    cleaned = raw_result.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:-3].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:-3].strip()
    return json.loads(cleaned)


def _generate_reply_and_title_for_new_session(history, message):
    raw_result = generate_chat_response(_build_new_session_title_prompt(history, message))
    try:
        data = _parse_send_message_json_result(raw_result)
        reply = data.get("reply", "")
        title = sanitize_session_title(data.get("title", "")) or "New Chat"
        return reply, title
    except Exception:
        return generate_chat_response(history), generate_session_title_from_message(message)


def _resolve_send_message_session_context(user, session_id):
    if not session_id:
        return None, []

    session = get_session_for_user(user, session_id)
    if session is None:
        return None, None
    return session, _build_session_message_history(session)


def _generate_send_message_reply_and_title(session, history, message):
    prepared_history = (
        build_history_with_summary(session, history) if session is not None else history
    )
    if session is None:
        return _generate_reply_and_title_for_new_session(prepared_history, message)
    return generate_chat_response(prepared_history), "New Chat"


def _sanitize_output_json(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    return {
        key: value
        for key, value in payload.items()
        if key not in REASONING_META_KEYS
    }


DEFAULT_EXPORT_TABLE_NAME = "Sheet1"
DEFAULT_EXPORT_VALUE_HEADER = "value"


def _get_cell_serialization_cache_key(value):
    if isinstance(value, bytes):
        return ("bytes", value)
    return ("object", id(value))


def _to_scalar_cell(value, serialization_cache=None):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    cache_key = None
    if serialization_cache is not None:
        cache_key = _get_cell_serialization_cache_key(value)
        cached_value = serialization_cache.get(cache_key)
        if cached_value is not None:
            return cached_value

    try:
        serialized_value = str(value) if isinstance(value, bytes) else json.dumps(value)
    except Exception:
        serialized_value = "[Unserializable Value]"

    if serialization_cache is not None and cache_key is not None:
        serialization_cache[cache_key] = serialized_value

    return serialized_value


def _normalize_headers(raw_headers):
    if not raw_headers:
        return [DEFAULT_EXPORT_VALUE_HEADER]

    counts = {}
    normalized = []
    for index, raw_header in enumerate(raw_headers):
        trimmed = (
            raw_header.strip()
            if isinstance(raw_header, str) and raw_header.strip()
            else f"column_{index + 1}"
        )
        key = trimmed.lower()
        count = counts.get(key, 0)
        counts[key] = count + 1
        normalized.append(trimmed if count == 0 else f"{trimmed}_{count + 1}")
    return normalized


def _map_array_row_to_object(row, headers, serialization_cache=None):
    return {
        header: _to_scalar_cell(
            row[index] if index < len(row) else None,
            serialization_cache=serialization_cache,
        )
        for index, header in enumerate(headers)
    }


def _map_object_row_to_object(row, headers, serialization_cache=None):
    return {
        header: _to_scalar_cell(row.get(header), serialization_cache=serialization_cache)
        for header in headers
    }


def _map_unknown_row_to_object(row, headers, serialization_cache=None):
    mapped_row = {}
    for index, header in enumerate(headers):
        mapped_row[header] = (
            _to_scalar_cell(row, serialization_cache=serialization_cache)
            if index == 0
            else None
        )
    return mapped_row


def _collect_rows_array_metadata(rows):
    all_lists = bool(rows)
    all_dicts = bool(rows)
    max_columns = 0
    collected_headers = []
    seen_headers = set()

    for row in rows:
        is_list_row = isinstance(row, list)
        is_dict_row = isinstance(row, dict)
        all_lists = all_lists and is_list_row
        all_dicts = all_dicts and is_dict_row

        if is_list_row:
            max_columns = max(max_columns, len(row))
        if is_dict_row:
            for key in row:
                if key not in seen_headers:
                    seen_headers.add(key)
                    collected_headers.append(key)

    return all_lists, all_dicts, max_columns, collected_headers


def _build_rows_from_generated_output_rows(rows, headers, serialization_cache=None):
    normalized_rows = []
    for row in rows:
        if isinstance(row, list):
            normalized_rows.append(
                _map_array_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
        elif isinstance(row, dict):
            normalized_rows.append(
                _map_object_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
        else:
            normalized_rows.append(
                _map_unknown_row_to_object(
                    row,
                    headers,
                    serialization_cache=serialization_cache,
                )
            )
    return normalized_rows


def _infer_headers_and_rows_from_rows_array(rows, serialization_cache=None):
    all_lists, all_dicts, max_columns, collected_headers = _collect_rows_array_metadata(rows)

    if all_lists:
        headers = _normalize_headers(
            [f"column_{index + 1}" for index in range(max_columns)]
        )
        return headers, _build_rows_from_generated_output_rows(
            rows,
            headers,
            serialization_cache=serialization_cache,
        )

    if all_dicts:
        headers = _normalize_headers(collected_headers)
        return headers, _build_rows_from_generated_output_rows(
            rows,
            headers,
            serialization_cache=serialization_cache,
        )

    headers = [DEFAULT_EXPORT_VALUE_HEADER]
    normalized_rows = [
        {
            DEFAULT_EXPORT_VALUE_HEADER: _to_scalar_cell(
                value,
                serialization_cache=serialization_cache,
            )
        }
        for value in rows
    ]
    return headers, normalized_rows


def _infer_headers_and_rows_from_output(output_json, serialization_cache=None):
    if isinstance(output_json, dict):
        headers = _normalize_headers(list(output_json.keys()))
        return headers, [
            _map_object_row_to_object(
                output_json,
                headers,
                serialization_cache=serialization_cache,
            )
        ]

    if isinstance(output_json, list):
        return _infer_headers_and_rows_from_rows_array(
            output_json,
            serialization_cache=serialization_cache,
        )

    return [DEFAULT_EXPORT_VALUE_HEADER], [
        {
            DEFAULT_EXPORT_VALUE_HEADER: _to_scalar_cell(
                output_json,
                serialization_cache=serialization_cache,
            )
        }
    ]


def _build_content_data_from_output(output_json, serialization_cache=None):
    if isinstance(output_json, dict):
        direct_headers = output_json.get("headers")
        direct_rows = output_json.get("rows")
        if isinstance(direct_headers, list) and isinstance(direct_rows, list):
            headers = _normalize_headers(direct_headers)
            return [
                {
                    "table_name": DEFAULT_EXPORT_TABLE_NAME,
                    "headers": headers,
                    "rows": _build_rows_from_generated_output_rows(
                        direct_rows,
                        headers,
                        serialization_cache=serialization_cache,
                    ),
                }
            ]

        entries = list(output_json.items())
        has_sheet_like_entries = entries and all(isinstance(value, list) for _, value in entries)
        if has_sheet_like_entries:
            content_data = []
            for index, (sheet_name, value) in enumerate(entries):
                headers, rows = _infer_headers_and_rows_from_rows_array(
                    value,
                    serialization_cache=serialization_cache,
                )
                table_name = (
                    sheet_name.strip()
                    if isinstance(sheet_name, str) and sheet_name.strip()
                    else f"Sheet{index + 1}"
                )
                content_data.append(
                    {
                        "table_name": table_name,
                        "headers": headers,
                        "rows": rows,
                    }
                )
            return content_data

    headers, rows = _infer_headers_and_rows_from_output(
        output_json,
        serialization_cache=serialization_cache,
    )
    return [
        {
            "table_name": DEFAULT_EXPORT_TABLE_NAME,
            "headers": headers,
            "rows": rows,
        }
    ]


def build_export_output_json(input_json, output_json):
    serialization_cache = {}
    content_data = _build_content_data_from_output(
        output_json,
        serialization_cache=serialization_cache,
    )

    total_rows = sum(len(table["rows"]) for table in content_data)
    total_columns = max((len(table["headers"]) for table in content_data), default=0)

    return {
        "document_info": {
            "source_type": _resolve_export_source_type(input_json, output_json),
            "filename": extract_original_name(input_json, output_json),
        },
        "summary": {
            "total_tables": len(content_data),
            "total_rows": total_rows,
            "total_columns": total_columns,
        },
        "content_data": content_data,
    }


def _generate_optional_reasoning(include_reasoning, input_json, output_json):
    if not include_reasoning:
        return None

    original_name = extract_original_name(input_json, output_json)
    document_type = _extract_document_type(input_json)
    reasoning_service = build_llm_reasoning_service()

    try:
        return generate_conversion_reasoning_response(
            reasoning_service=reasoning_service,
            input_json=input_json,
            output_json=output_json,
            file_name=original_name,
            document_type=document_type,
        )
    except (OpenAIServiceError, ValueError):
        logger.exception("Automatic reasoning failed while handling llm_generate request.")
        return None
    except Exception:
        logger.exception("Unexpected error while generating automatic reasoning.")
        return None


def _thinking_log_not_found_response():
    return Response({"detail": THINKING_LOG_NOT_FOUND_DETAIL}, status=404)


def _invalid_thinking_log_pagination_response():
    return Response(
        {
            "detail": INVALID_REQUEST_DETAIL,
            "errors": {
                "pagination": [INVALID_THINKING_LOG_PAGINATION_DETAIL],
            },
        },
        status=400,
    )


def _invalid_thinking_log_identifier_response(field_name: str):
    return Response(
        {
            "detail": INVALID_REQUEST_DETAIL,
            "errors": {
                field_name: [INVALID_THINKING_LOG_IDENTIFIER_DETAIL],
            },
        },
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
    queryset = GeneratedOutput.objects.filter(session__owner=user).exclude(thinking_log="")

    if session_id:
        queryset = queryset.filter(session_id=session_id)

    identifier = chat_id or request_id
    if identifier:
        queryset = queryset.filter(id=identifier)

    return queryset.defer("export_output_json").order_by("-created_at", "-id")


def _resolve_generate_session(user, session_id):
    if session_id is None or not getattr(user, "is_authenticated", False):
        return None, None

    session = get_session_for_user(user, session_id)
    if session is None:
        return None, Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)

    return session, None


def _generate_output_json(llm_generation_service, input_json, custom_schema_id):
    try:
        return llm_generation_service.generate(
            input_json=input_json,
            custom_schema_id=custom_schema_id,
        ), None
    except CustomSchemaNotFoundError:
        return None, Response({"detail": CUSTOM_SCHEMA_NOT_FOUND_DETAIL}, status=404)
    except OpenAIConfigurationError:
        return None, Response({"detail": SERVICE_UNAVAILABLE_DETAIL}, status=503)
    except OpenAIUpstreamError as exc:
        logger.exception("Upstream LLM provider error while handling llm_generate request.")
        return None, Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=exc.status_code)
    except OpenAIServiceError:
        return None, Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    except ValueError:
        logger.exception("Invalid input_json payload.")
        return None, Response(
            {
                "detail": INVALID_REQUEST_DETAIL,
                "errors": {"input_json": [INVALID_INPUT_JSON_DETAIL]},
            },
            status=400,
        )
    except Exception:
        logger.exception("Unexpected error while handling llm_generate request.")
        return None, Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)


def _persist_generate_output_for_authenticated_user(
    user,
    session,
    output_json,
    thinking_log,
    export_output_json,
    title="",
):
    if not getattr(user, "is_authenticated", False):
        return None, None, None

    try:
        with transaction.atomic():
            if session is None:
                session = create_session_for_user(user, title=title)
            generated_output = create_generated_output(
                session,
                output_json,
                thinking_log=thinking_log,
                export_output_json=export_output_json,
            )
        return session.id, generated_output.id, None
    except Exception:
        logger.exception(
            "Unexpected error while persisting session-aware llm_generate output."
        )
        return None, None, Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)


def _build_generate_success_response(output_json, session_id, output_id, reasoning):
    response_serializer = LlmGenerateResponseSerializer(
        data={
            "output_json": output_json,
            "session_id": session_id,
            "output_id": output_id,
            "reasoning": reasoning,
        }
    )
    if not response_serializer.is_valid():
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    return Response(response_serializer.data)


@api_view(["POST"])
@require_http_methods(["POST"])
def llm_generate(request):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != _JSON_CONTENT_TYPE:
        return Response({"detail": UNSUPPORTED_MEDIA_TYPE_DETAIL}, status=415)

    request_serializer = LlmGenerateRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {"detail": INVALID_REQUEST_DETAIL, "errors": request_serializer.errors},
            status=400,
        )

    validated_data = cast(dict[str, Any], request_serializer.validated_data)
    input_json = validated_data["input_json"]
    session_id = validated_data.get("session_id")
    custom_schema_id = validated_data.get("custom_schema_id")
    session, error_response = _resolve_generate_session(request.user, session_id)
    if error_response is not None:
        return error_response
    include_reasoning = validated_data.get("include_reasoning", True)
    llm_generation_service = build_llm_generation_service(request.user)
    output_json, error_response = _generate_output_json(
        llm_generation_service,
        input_json,
        custom_schema_id,
    )
    if error_response is not None:
        return error_response

    output_json = _sanitize_output_json(output_json)
    export_output_json = build_export_output_json(
        input_json=input_json,
        output_json=output_json,
    )
    reasoning_response = _generate_optional_reasoning(
        include_reasoning=include_reasoning,
        input_json=input_json,
        output_json=output_json,
    )
    thinking_log = ""
    if isinstance(reasoning_response, dict):
        raw_thinking_log = reasoning_response.get("thinking_log")
        if isinstance(raw_thinking_log, str):
            thinking_log = raw_thinking_log

    response_session_id, response_output_id, error_response = _persist_generate_output_for_authenticated_user(
        request.user,
        session,
        output_json,
        thinking_log,
        export_output_json,
        title=resolve_session_title(f"Convert {extract_original_name(input_json, output_json)}"),
    )
    if error_response is not None:
        return error_response

    if getattr(request.user, "is_authenticated", False):
        create_artifact_history(
            owner=request.user,
            original_name=extract_original_name(input_json, output_json),
            custom_name=None,
            output_json=output_json,
            status_processing="completed",
        )

    return _build_generate_success_response(
        output_json,
        response_session_id,
        response_output_id,
        reasoning_response,
    )

@require_http_methods(["POST"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_message(request):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != _JSON_CONTENT_TYPE:
        return Response({"detail": UNSUPPORTED_MEDIA_TYPE_DETAIL}, status=415)

    serializer = SendMessageRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"detail": INVALID_REQUEST_DETAIL, "errors": serializer.errors},
            status=400,
        )

    message = serializer.validated_data["message"]
    session_id = serializer.validated_data.get("session_id")
    session, history = _resolve_send_message_session_context(request.user, session_id)
    if session_id and session is None:
        return Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)

    history.append({"role": "user", "content": message})

    try:
        reply, title = _generate_send_message_reply_and_title(session, history, message)
    except OpenAIConfigurationError:
        return Response({"detail": SERVICE_UNAVAILABLE_DETAIL}, status=503)
    except OpenAIUpstreamError as exc:
        logger.exception("Upstream LLM provider error while handling send_message request.")
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=exc.status_code)
    except OpenAIServiceError:
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    except Exception:
        logger.exception("Unexpected error while handling send_message request.")
        return Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)

    with transaction.atomic():
        if session is None:
            session = create_session_for_user(request.user, title=title)
        append_user_message(session, message)
        append_assistant_message(session, reply)

    response_serializer = SendMessageResponseSerializer(
        data={"session_id": session.id, "reply": reply}
    )
    if not response_serializer.is_valid():
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    return Response(response_serializer.data)


@require_http_methods(["POST"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def llm_reasoning(request):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != _JSON_CONTENT_TYPE:
        return Response({"detail": UNSUPPORTED_MEDIA_TYPE_DETAIL}, status=415)

    request_serializer = LlmReasoningRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {"detail": INVALID_REQUEST_DETAIL, "errors": request_serializer.errors},
            status=400,
        )

    validated_data = cast(dict[str, Any], request_serializer.validated_data)
    prompt = validated_data["prompt"]
    reasoning_service = build_llm_reasoning_service()

    try:
        reasoning_response = generate_reasoning_response(
            reasoning_service=reasoning_service,
            prompt=prompt,
        )
    except OpenAIConfigurationError:
        return Response({"detail": SERVICE_UNAVAILABLE_DETAIL}, status=503)
    except OpenAIUpstreamError as exc:
        logger.exception("Upstream LLM provider error while handling llm_reasoning request.")
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=exc.status_code)
    except OpenAIServiceError:
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    except ValueError:
        logger.exception("Invalid prompt payload.")
        return Response(
            {
                "detail": INVALID_REQUEST_DETAIL,
                "errors": {"prompt": [INVALID_PROMPT_DETAIL]},
            },
            status=400,
        )
    except Exception:
        logger.exception("Unexpected error while handling llm_reasoning request.")
        return Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)

    response_serializer = LlmReasoningResponseSerializer(data=reasoning_response)
    if not response_serializer.is_valid():
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)

    return Response(response_serializer.data)


@api_view(["GET"])
@require_http_methods(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def thinking_log_list(request):
    try:
        page = _parse_thinking_log_positive_int(request.query_params.get("page"), default=1)
        page_size = _parse_thinking_log_page_size(
            request.query_params.get("page_size"),
            default=10,
        )
    except (TypeError, ValueError):
        return _invalid_thinking_log_pagination_response()

    session_id = request.query_params.get("session_id")
    chat_id = request.query_params.get("chat_id")
    request_id = request.query_params.get("request_id")

    try:
        parsed_session_id = _parse_thinking_log_identifier(session_id, "session_id")
        parsed_chat_id = _parse_thinking_log_identifier(chat_id, "chat_id")
        parsed_request_id = _parse_thinking_log_identifier(request_id, "request_id")
    except ValueError as exc:
        return _invalid_thinking_log_identifier_response(str(exc))

    queryset = _build_thinking_log_queryset_for_user(
        user=request.user,
        session_id=parsed_session_id,
        chat_id=parsed_chat_id,
        request_id=parsed_request_id,
    )

    total_count = queryset.count()
    offset = (page - 1) * page_size
    paged_records = queryset[offset : offset + page_size]

    return Response(
        {
            "count": total_count,
            "page": page,
            "page_size": page_size,
            "results": ThinkingLogItemSerializer(paged_records, many=True).data,
        },
        status=200,
    )


@api_view(["GET"])
@require_http_methods(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def thinking_log_detail(request, history_id):
    record = _build_thinking_log_queryset_for_user(
        user=request.user,
        chat_id=history_id,
    ).first()
    if record is None:
        return _thinking_log_not_found_response()

    return Response(ThinkingLogItemSerializer(record).data, status=200)
