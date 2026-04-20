from django.conf import settings
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from monitoring.container import get_monitoring_service


def _is_authorized(request) -> bool:
    expected_token = (getattr(settings, "MONITORING_API_TOKEN", "") or "").strip()
    if not expected_token:
        return True

    provided_token = (request.headers.get("X-Monitoring-Token", "") or "").strip()
    return provided_token == expected_token


@require_GET
@api_view(["GET"])
def live(request):
    payload = get_monitoring_service().live()
    return Response(payload, status=status.HTTP_200_OK)


@require_GET
@api_view(["GET"])
def ready(request):
    http_status, payload = get_monitoring_service().readiness()
    return Response(payload, status=http_status)


@require_GET
@api_view(["GET"])
def stats(request):
    if not _is_authorized(request):
        return Response(
            {
                "status": "error",
                "message": "Unauthorized monitoring access.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    payload = get_monitoring_service().stats()
    return Response(payload, status=status.HTTP_200_OK)
