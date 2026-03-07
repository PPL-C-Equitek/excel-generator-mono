from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.decorators import rate_limit
from .serializers import LlmGenerateRequestSerializer, LlmGenerateResponseSerializer
from .services.openai_client import OpenAIConfigurationError, OpenAIServiceError, generate_json


@api_view(["POST"])
@rate_limit(max_requests=5, per="minute")
@require_http_methods(["POST"])
def llm_generate(request):
    request_serializer = LlmGenerateRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response({"detail": "Invalid request payload."}, status=400)

    input_json = request_serializer.validated_data["input_json"]
    try:
        output_json = generate_json(input_json=input_json)
    except OpenAIConfigurationError:
        return Response({"detail": "Service unavailable. Please try again later."}, status=503)
    except OpenAIServiceError:
        return Response({"detail": "Failed to generate response from OpenAI."}, status=502)
    except ValueError:
        return Response({"detail": "Invalid request payload."}, status=400)
    except Exception:
        return Response({"detail": "Failed to generate response from OpenAI."}, status=502)

    response_serializer = LlmGenerateResponseSerializer(data={"output_json": output_json})
    if not response_serializer.is_valid():
        return Response({"detail": "Failed to generate response from OpenAI."}, status=502)
    return Response(response_serializer.data)
