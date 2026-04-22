from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from authentication.jwt_authentication import JWTAuthentication
from monitoring.application.access_policy import MonitoringAccessPolicy
from monitoring.container import get_monitoring_service
from monitoring.interfaces.http.decorators import monitoring_protected_get


@require_GET
@api_view(["GET"])
def live(request):
    payload = get_monitoring_service().live()
    return Response(payload, status=status.HTTP_200_OK)


@monitoring_protected_get
def ready(request):
    http_status, payload = get_monitoring_service().readiness()
    return Response(payload, status=http_status)


@monitoring_protected_get
def stats(request):
    payload = get_monitoring_service().stats()
    return Response(payload, status=status.HTTP_200_OK)


@require_GET
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
def access(request):
    decision = MonitoringAccessPolicy().evaluate(getattr(request, "user", None))
    return Response(
        decision.to_dict(),
        status=status.HTTP_200_OK,
    )
