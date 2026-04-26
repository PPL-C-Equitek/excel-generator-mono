import logging
from typing import Any, cast
from uuid import UUID

from chat_sessions.models import ChatMessage
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from artifact_history.services import create_artifact_history
from chat_sessions.services import (
    append_assistant_message,
    append_user_message,
    build_history_with_summary,
    create_session_for_user,
    get_session_for_user,
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
    FALLBACK_FINAL_ANSWER,
    FALLBACK_REASONING_STEP,
    FALLBACK_THINKING_LOG,
    LlmReasoningService,
    build_storage_thinking_log,
    generate_conversion_reasoning_response,
    parse_reasoning_response,
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

    for key in ("document_type", "file_type", "format"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    return "unknown"


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


def _is_fallback_reasoning_payload(reasoning_payload: Any) -> bool:
    if not isinstance(reasoning_payload, dict):
        return True

    final_answer = reasoning_payload.get("final_answer")
    thinking_log = reasoning_payload.get("thinking_log")
    reasoning_steps = reasoning_payload.get("reasoning_steps")

    return (
        final_answer == FALLBACK_FINAL_ANSWER
        and thinking_log == FALLBACK_THINKING_LOG
        and reasoning_steps == [FALLBACK_REASONING_STEP]
    )


def _extract_reasoning_payload_from_chat_reply(reply: str) -> dict[str, Any] | None:
    if not isinstance(reply, str) or not reply.strip():
        return None

    try:
        parsed = parse_reasoning_response(reply)
    except Exception:
        logger.exception("Failed to parse chat reasoning payload from assistant reply.")
        return None

    if _is_fallback_reasoning_payload(parsed):
        return None

    return parsed


def _save_thinking_log_for_message(message: ChatMessage, thinking_log: str) -> None:
    normalized_log = thinking_log.strip() if isinstance(thinking_log, str) else ""
    if not normalized_log:
        return

    try:
        message.thinking_log = normalized_log
        message.save(update_fields=["thinking_log"])
    except Exception:
        logger.exception("Failed to persist thinking_log for chat message.")


def _capture_generate_reasoning_thinking_log(
    *,
    user,
    input_json,
    output_json,
    reasoning_response,
) -> None:
    if not getattr(user, "is_authenticated", False):
        return
    if not isinstance(reasoning_response, dict):
        return

    thinking_log = build_storage_thinking_log(reasoning_response)
    if not thinking_log:
        return

    try:
        with transaction.atomic():
            session = create_session_for_user(
                user,
                title=extract_original_name(input_json, output_json),
            )
            final_answer = reasoning_response.get("final_answer")
            assistant_content = (
                final_answer.strip()
                if isinstance(final_answer, str) and final_answer.strip()
                else "Output berhasil dihasilkan."
            )
            assistant_message = append_assistant_message(session, assistant_content)
            _save_thinking_log_for_message(assistant_message, thinking_log)
    except Exception:
        logger.exception("Failed to capture reasoning thinking_log for llm_generate.")


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
    queryset = ChatMessage.objects.filter(session__owner=user).exclude(thinking_log="")

    normalized_session_id = session_id.strip() if isinstance(session_id, str) else ""
    if normalized_session_id:
        queryset = queryset.filter(session_id=normalized_session_id)

    identifier = chat_id or request_id
    if identifier:
        queryset = queryset.filter(id=identifier)

    return queryset.order_by("-created_at", "-id")


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
    custom_schema_id = validated_data.get("custom_schema_id")
    include_reasoning = validated_data.get("include_reasoning", True)
    llm_generation_service = build_llm_generation_service(request.user)

    try:
        output_json = llm_generation_service.generate(
            input_json=input_json,
            custom_schema_id=custom_schema_id,
        )
        output_json = _sanitize_output_json(output_json)
    except CustomSchemaNotFoundError:
        return Response({"detail": CUSTOM_SCHEMA_NOT_FOUND_DETAIL}, status=404)
    except OpenAIConfigurationError:
        return Response({"detail": SERVICE_UNAVAILABLE_DETAIL}, status=503)
    except OpenAIUpstreamError as exc:
        logger.exception("Upstream LLM provider error while handling llm_generate request.")
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=exc.status_code)
    except OpenAIServiceError:
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    except ValueError:
        logger.exception("Invalid input_json payload.")
        return Response(
            {
                "detail": INVALID_REQUEST_DETAIL,
                "errors": {"input_json": [INVALID_INPUT_JSON_DETAIL]},
            },
            status=400,
        )
    except Exception:
        logger.exception("Unexpected error while handling llm_generate request.")
        return Response({"detail": INTERNAL_FAILURE_DETAIL}, status=500)

    reasoning_response = _generate_optional_reasoning(
        include_reasoning=include_reasoning,
        input_json=input_json,
        output_json=output_json,
    )

    response_serializer = LlmGenerateResponseSerializer(
        data={
            "output_json": output_json,
            "reasoning": reasoning_response,
        }
    )
    if not response_serializer.is_valid():
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)

    if getattr(request.user, "is_authenticated", False):
        create_artifact_history(
            owner=request.user,
            original_name=extract_original_name(input_json, output_json),
            custom_name=None,
            output_json=output_json,
            status_processing="completed",
        )
        try:
            _capture_generate_reasoning_thinking_log(
                user=request.user,
                input_json=input_json,
                output_json=output_json,
                reasoning_response=reasoning_response,
            )
        except Exception:
            logger.exception("Unexpected failure while capturing llm_generate reasoning log.")
    return Response(response_serializer.data)

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

    session = None
    if session_id:
        session = get_session_for_user(request.user, session_id)
        if session is None:
            return Response({"detail": SESSION_NOT_FOUND_DETAIL}, status=404)
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages.order_by("created_at")
        ]
    else:
        history = []

    history.append({"role": "user", "content": message})

    try:
        if session is not None:
            history = build_history_with_summary(session, history)
        reply = generate_chat_response(history)
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

    parsed_reasoning = _extract_reasoning_payload_from_chat_reply(reply)
    thinking_log = build_storage_thinking_log(parsed_reasoning)

    with transaction.atomic():
        if session is None:
            session = create_session_for_user(request.user)
        append_user_message(session, message)
        assistant_message = append_assistant_message(session, reply)

    _save_thinking_log_for_message(assistant_message, thinking_log)

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
        parsed_chat_id = _parse_thinking_log_identifier(chat_id, "chat_id")
        parsed_request_id = _parse_thinking_log_identifier(request_id, "request_id")
    except ValueError as exc:
        return _invalid_thinking_log_identifier_response(str(exc))

    queryset = _build_thinking_log_queryset_for_user(
        user=request.user,
        session_id=session_id,
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
