import logging
from typing import Any, cast

from artifact_history.models import ArtifactHistory
from django.conf import settings
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
    LlmReasoningService,
    generate_conversion_reasoning_response,
    generate_reasoning_response,
)
from .services.refinement_service import (
    RefinementConfig,
    RefinementOrchestrator,
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


def _build_thinking_log_queryset_for_user(user, session_id=None, request_id=None):
    queryset = ArtifactHistory.objects.filter(owner=user)

    normalized_session_id = session_id.strip() if isinstance(session_id, str) else ""
    normalized_request_id = request_id.strip() if isinstance(request_id, str) else ""

    if normalized_session_id:
        queryset = queryset.filter(output_json__session_id=normalized_session_id)

    if normalized_request_id:
        queryset = queryset.filter(output_json__request_id=normalized_request_id)

    return queryset


def _should_expose_validation_log() -> bool:
    return bool(getattr(settings, "LLM_EXPOSE_VALIDATION_LOG", False))


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
    refinement_payload = validated_data.get("refinement", {})
    refinement_enabled = bool(refinement_payload.get("enabled", False))
    llm_generation_service = build_llm_generation_service(request.user)

    try:
        if refinement_enabled:
            refinement_config = RefinementConfig(
                enabled=True,
                max_iterations=int(refinement_payload.get("max_iterations", 3)),
                early_exit_on_valid=bool(
                    refinement_payload.get("early_exit_on_valid", True)
                ),
            )
            refinement_orchestrator = RefinementOrchestrator(
                generation_service=llm_generation_service,
                reasoning_service=(
                    build_llm_reasoning_service() if include_reasoning else None
                ),
            )
            refinement_result = refinement_orchestrator.run(
                input_json=input_json,
                custom_schema_id=custom_schema_id,
                include_reasoning=include_reasoning,
                refinement_config=refinement_config,
                file_name=extract_original_name(input_json, input_json),
                document_type=_extract_document_type(input_json),
            )
            output_json = _sanitize_output_json(refinement_result["output_json"])
            raw_json = _sanitize_output_json(refinement_result["raw_json"])
            validated_json = _sanitize_output_json(refinement_result["validated_json"])
            validation_log = refinement_result["validation_log"]
            reasoning_response = refinement_result["reasoning"]
            refinement_meta = refinement_result["refinement_meta"]
        else:
            output_json = llm_generation_service.generate(
                input_json=input_json,
                custom_schema_id=custom_schema_id,
            )
            output_json = _sanitize_output_json(output_json)
            raw_json = None
            validated_json = None
            validation_log = None
            refinement_meta = None
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

    if not refinement_enabled:
        reasoning_response = _generate_optional_reasoning(
            include_reasoning=include_reasoning,
            input_json=input_json,
            output_json=output_json,
        )

    response_payload = {
        "output_json": output_json,
        "reasoning": reasoning_response,
    }
    if refinement_enabled:
        refinement_payload = {
            "validated_json": validated_json,
        }
        if _should_expose_validation_log():
            refinement_payload["raw_json"] = raw_json
            refinement_payload["validation_log"] = validation_log
            refinement_payload["refinement_meta"] = refinement_meta
        response_payload.update(refinement_payload)

    response_serializer = LlmGenerateResponseSerializer(data=response_payload)
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

    with transaction.atomic():
        if session is None:
            session = create_session_for_user(request.user)
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
    request_id = request.query_params.get("request_id")
    queryset = _build_thinking_log_queryset_for_user(
        user=request.user,
        session_id=session_id,
        request_id=request_id,
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
    record = ArtifactHistory.objects.filter(owner=request.user, id=history_id).first()
    if record is None:
        return _thinking_log_not_found_response()

    return Response(ThinkingLogItemSerializer(record).data, status=200)
