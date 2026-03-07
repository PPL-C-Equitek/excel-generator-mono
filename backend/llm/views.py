from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import LlmGenerateRequestSerializer, LlmGenerateResponseSerializer
from .services.openai_client import OpenAIServiceError, generate_json


@api_view(["POST"])
@require_http_methods(["POST"])
def llm_generate(request):
    request_serializer = LlmGenerateRequestSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)

    input_json = request_serializer.validated_data["input_json"]
    try:
        output_json = generate_json(input_json=input_json)
    except OpenAIServiceError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        if status_code == 503:
            detail = "Service unavailable. Please try again later."
        else:
            detail = "Failed to generate response from OpenAI."
        return Response({"detail": detail}, status=status_code)
    except ValueError:
        return Response({"detail": "Invalid request payload."}, status=400)
    except Exception:
        return Response({"detail": "Failed to generate response from OpenAI."}, status=502)

    response_serializer = LlmGenerateResponseSerializer(data={"output_json": output_json})
    response_serializer.is_valid(raise_exception=True)
    return Response(response_serializer.data)