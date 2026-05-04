import json
import logging
from typing import Any, cast
from uuid import UUID

from chat_sessions.models import GeneratedOutput
from artifact_history.services import create_artifact_history
from django.conf import settings
from django.db import transaction
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat_sessions.models import ChatMessage
from chat_sessions.services import (
    append_assistant_message,
    append_user_message,
    build_history_with_summary,
    create_generated_output,
    create_session_for_user,
    generate_session_title_from_message,
    get_chat_message_for_user,
    get_generated_output_for_user,
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

from .services.export_service import (
    _extract_document_type,
    _extract_document_info_filename,
    _normalize_filename_candidate,
    build_export_output_json,
    extract_original_name,
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


def _build_table_context_lines(table: dict) -> list:
    table_name = table.get("table_name", "Sheet")
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    lines = [f"Table '{table_name}': {len(headers)} columns, {len(rows)} rows"]
    if headers:
        lines.append(f"  Headers: {', '.join(str(h) for h in headers)}")
    for i, row in enumerate(rows[:3]):
        if isinstance(row, dict):
            sample = dict(list(row.items())[:5])
            lines.append(f"  Row {i + 1}: {json.dumps(sample)}")
    return lines


def _build_compact_file_context(export_json: dict) -> str:
    lines = [
        "[CONVERTED_FILE_CONTEXT]",
        "The user is reviewing a converted file. "
        "Use the metadata and samples below to answer questions about the file.",
    ]
    doc_info = export_json.get("document_info")
    if isinstance(doc_info, dict):
        filename = doc_info.get("filename", "unknown")
        source_type = doc_info.get("source_type", "unknown")
        lines.append(f"File: {filename} ({source_type})")

    summary = export_json.get("summary")
    if isinstance(summary, dict) and summary:
        parts = [f"{k}={v}" for k, v in summary.items()]
        lines.append("Summary: " + ", ".join(parts))

    content_data = export_json.get("content_data")
    if isinstance(content_data, list):
        for table in content_data:
            if isinstance(table, dict):
                lines.extend(_build_table_context_lines(table))

    return "\n".join(lines)


def _inject_file_context_if_available(session, history: list) -> list:
    if session is None:
        return history
    last_output = session.generated_outputs.order_by("-created_at").first()
    if last_output is None:
        return history
    export_json = last_output.export_output_json or {}
    if not export_json:
        raw = getattr(last_output, "output_json", None)
        if raw:
            export_json = build_export_output_json(input_json=raw, output_json=raw)
    if not export_json:
        return history
    return [{"role": "system", "content": _build_compact_file_context(export_json)}] + history


def _generate_send_message_reply_and_title(session, history, message):
    prepared_history = (
        build_history_with_summary(session, history) if session is not None else history
    )
    prepared_history = _inject_file_context_if_available(session, prepared_history)
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

    if chat_id:
        queryset = queryset.filter(source_message_id=chat_id)
    elif request_id:
        queryset = queryset.filter(id=request_id)

    return queryset.defer("export_output_json").order_by("-created_at", "-id")


def _resolve_generate_session(user, session_id):
    if session_id is None or not getattr(user, "is_authenticated", False):
        return None, None

    session = get_session_for_user(user, session_id)
    if session is None:
        return None, Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)

    return session, None


def _build_chat_context_from_session(session) -> str | None:
    if session is None:
        return None
    max_instructions = max(1, getattr(settings, "CHAT_CONTEXT_MAX_USER_INSTRUCTIONS", 5))
    recent = list(
        session.messages
        .filter(role=ChatMessage.ROLE_USER)
        .order_by("-created_at")[:max_instructions]
    )
    if not recent:
        return None
    recent.reverse()
    return "\n".join(f"USER: {msg.content}" for msg in recent)


def _resolve_message_target_output(user, session, target_output_id):
    if target_output_id is None:
        return None, None

    target_output = get_generated_output_for_user(user, target_output_id)
    if target_output is None:
        return None, Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)
    if session is not None and target_output.session_id != session.id:
        return None, Response(
            {
                "detail": INVALID_REQUEST_DETAIL,
                "errors": {"target_output_id": ["target_output_id must belong to the same session."]},
            },
            status=400,
        )
    return target_output, None


def _resolve_generate_source_message(user, session, chat_id):
    if chat_id is None:
        return None, session, None

    source_message = get_chat_message_for_user(user, chat_id)
    if source_message is None:
        return None, session, Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)
    if session is not None and source_message.session_id != session.id:
        return None, session, Response(
            {
                "detail": INVALID_REQUEST_DETAIL,
                "errors": {"chat_id": ["chat_id must belong to the same session."]},
            },
            status=400,
        )
    return source_message, source_message.session, None


def _generate_output_json(llm_generation_service, input_json, custom_schema_id, chat_context=None):
    try:
        return llm_generation_service.generate(
            input_json=input_json,
            custom_schema_id=custom_schema_id,
            chat_context=chat_context,
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
    reasoning,
    export_output_json,
    source_message=None,
    parent_output=None,
    bootstrap_message_content="",
    title="",
):
    if not getattr(user, "is_authenticated", False):
        return None, None, None, None

    try:
        with transaction.atomic():
            created_new_session = session is None
            if session is None:
                session = create_session_for_user(user, title=title)
            if created_new_session and source_message is None:
                source_message = append_user_message(
                    session,
                    bootstrap_message_content,
                )
            generated_output = create_generated_output(
                session,
                output_json,
                thinking_log=thinking_log,
                reasoning=reasoning,
                export_output_json=export_output_json,
                source_message=source_message,
                parent_output=parent_output,
            )
        return session.id, generated_output.id, source_message.id if source_message else None, None
    except Exception:
        logger.exception(
            "Unexpected error while persisting session-aware llm_generate output."
        )
        return None, None, None, Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)


def _build_generate_bootstrap_message(input_json, title):
    filename = None
    if isinstance(input_json, dict):
        filename = _normalize_filename_candidate(input_json.get("filename"))
        if filename is None:
            filename = _extract_document_info_filename(input_json)
    if filename:
        return f"Uploaded file: {filename}"
    if title:
        return title
    return "Uploaded file for conversion"


def _extract_follow_up_prompt(input_json):
    if not isinstance(input_json, dict):
        return ""

    prompt = input_json.get("user_prompt")
    if not isinstance(prompt, str):
        return ""

    return prompt.strip()


def _build_generate_success_response(output_json, session_id, chat_id, output_id, reasoning):
    response_serializer = LlmGenerateResponseSerializer(
        data={
            "output_json": output_json,
            "session_id": session_id,
            "chat_id": chat_id,
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
    chat_id = validated_data.get("chat_id")
    custom_schema_id = validated_data.get("custom_schema_id")
    session, error_response = _resolve_generate_session(request.user, session_id)
    if error_response is not None:
        return error_response
    source_message, session, error_response = _resolve_generate_source_message(
        request.user,
        session,
        chat_id,
    )
    if error_response is not None:
        return error_response
    include_reasoning = validated_data.get("include_reasoning", True)
    chat_context = _build_chat_context_from_session(session)
    llm_generation_service = build_llm_generation_service(request.user)
    output_json, error_response = _generate_output_json(
        llm_generation_service,
        input_json,
        custom_schema_id,
        chat_context=chat_context,
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

    follow_up_prompt = _extract_follow_up_prompt(input_json)
    if (
        session is not None
        and source_message is None
        and follow_up_prompt
        and getattr(request.user, "is_authenticated", False)
    ):
        source_message = append_user_message(
            session,
            follow_up_prompt,
        )

    response_session_id, response_output_id, response_chat_id, error_response = _persist_generate_output_for_authenticated_user(
        request.user,
        session,
        output_json,
        thinking_log,
        reasoning_response,
        export_output_json,
        source_message=source_message,
        parent_output=getattr(source_message, "target_output", None),
        bootstrap_message_content=_build_generate_bootstrap_message(
            input_json,
            resolve_session_title(f"Convert {extract_original_name(input_json, output_json)}"),
        ),
        title=resolve_session_title(f"Convert {extract_original_name(input_json, output_json)}"),
    )
    if error_response is not None:
        return error_response

    if getattr(request.user, "is_authenticated", False):
        create_artifact_history(
            owner=request.user,
            original_name=extract_original_name(input_json, output_json),
            custom_name=None,
            session_id=response_session_id,
            output_json=output_json,
            status_processing="completed",
        )

    return _build_generate_success_response(
        output_json,
        response_session_id,
        response_chat_id,
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
    target_output_id = serializer.validated_data.get("target_output_id")
    session, history = _resolve_send_message_session_context(request.user, session_id)
    if session_id and session is None:
        return Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)
    target_output, error_response = _resolve_message_target_output(
        request.user,
        session,
        target_output_id,
    )
    if error_response is not None:
        return error_response
    if session is None and target_output is not None:
        session = target_output.session
        history = _build_session_message_history(session)

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
        user_message = append_user_message(
            session,
            message,
            target_output=target_output,
        )
        append_assistant_message(session, reply)

    response_serializer = SendMessageResponseSerializer(
        data={"session_id": session.id, "chat_id": user_message.id, "reply": reply}
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
def thinking_log_session_list(request, session_id):
    try:
        page = _parse_thinking_log_positive_int(request.query_params.get("page"), default=1)
        page_size = _parse_thinking_log_page_size(
            request.query_params.get("page_size"),
            default=10,
        )
    except (TypeError, ValueError):
        return _invalid_thinking_log_pagination_response()

    queryset = _build_thinking_log_queryset_for_user(
        user=request.user,
        session_id=session_id,
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
def thinking_log_detail(request, output_id):
    record = _build_thinking_log_queryset_for_user(
        user=request.user,
        request_id=output_id,
    ).first()
    if record is None:
        return _thinking_log_not_found_response()

    return Response(ThinkingLogItemSerializer(record).data, status=200)
