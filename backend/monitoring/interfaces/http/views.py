from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.jwt_authentication import JWTAuthentication
from monitoring.container import get_monitoring_service
from monitoring.interfaces.http.permissions import IsMonitoringAccount


@require_GET
@api_view(["GET"])
def live(request):
    payload = get_monitoring_service().live()
    return Response(payload, status=status.HTTP_200_OK)


@require_GET
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsMonitoringAccount])
def ready(request):
    http_status, payload = get_monitoring_service().readiness()
    return Response(payload, status=http_status)


@require_GET
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsMonitoringAccount])
def stats(request):
    payload = get_monitoring_service().stats()
    return Response(payload, status=status.HTTP_200_OK)
