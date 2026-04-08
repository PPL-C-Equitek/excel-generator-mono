import logging

from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import LlmGenerateRequestSerializer, LlmGenerateResponseSerializer
from .services.generation_service import (
    CustomSchemaNotFoundError,
    DjangoCustomSchemaPromptSource,
    JsonGenerationService,
    LlmGenerationService,
)
from .services.openai_client import (
    OpenAITextGenerationProvider,
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
)

logger = logging.getLogger(__name__)

INVALID_REQUEST_DETAIL = "Invalid request payload."
UNSUPPORTED_MEDIA_TYPE_DETAIL = "Content-Type must be application/json."
SERVICE_UNAVAILABLE_DETAIL = "Service unavailable. Please try again later."
UPSTREAM_FAILURE_DETAIL = "Failed to generate response from LLM provider."
INTERNAL_FAILURE_DETAIL = "Internal server error."
INVALID_INPUT_JSON_DETAIL = "Invalid input_json payload."
CUSTOM_SCHEMA_NOT_FOUND_DETAIL = "Custom schema not found."


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


@api_view(["POST"])
@require_http_methods(["POST"])
def llm_generate(request):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return Response({"detail": UNSUPPORTED_MEDIA_TYPE_DETAIL}, status=415)

    request_serializer = LlmGenerateRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {"detail": INVALID_REQUEST_DETAIL, "errors": request_serializer.errors},
            status=400,
        )

    input_json = request_serializer.validated_data["input_json"]
    custom_schema_id = request_serializer.validated_data.get("custom_schema_id")
    llm_generation_service = build_llm_generation_service(request.user)

    try:
        output_json = llm_generation_service.generate(
            input_json=input_json,
            custom_schema_id=custom_schema_id,
        )
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

    response_serializer = LlmGenerateResponseSerializer(data={"output_json": output_json})
    if not response_serializer.is_valid():
        return Response({"detail": UPSTREAM_FAILURE_DETAIL}, status=502)
    return Response(response_serializer.data)
