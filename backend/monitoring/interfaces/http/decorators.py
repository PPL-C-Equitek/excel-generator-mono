from collections.abc import Callable
from typing import Any

from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from authentication.jwt_authentication import JWTAuthentication
from monitoring.interfaces.http.permissions import IsMonitoringAccount


def monitoring_protected_get(view_func: Callable[..., Any]):
    decorated = permission_classes([IsAuthenticated, IsMonitoringAccount])(view_func)
    decorated = authentication_classes([JWTAuthentication])(decorated)
    decorated = api_view(["GET"])(decorated)
    decorated = require_GET(decorated)
    return decorated

