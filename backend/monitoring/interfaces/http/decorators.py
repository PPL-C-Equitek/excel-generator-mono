from collections.abc import Callable
from functools import wraps
from typing import Any

from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from authentication.jwt_authentication import JWTAuthentication
from monitoring.container import get_monitoring_service
from monitoring.interfaces.http.permissions import IsMonitoringAccount


def monitoring_protected_get(view_func: Callable[..., Any]):
    decorated = permission_classes([IsAuthenticated, IsMonitoringAccount])(view_func)
    decorated = authentication_classes([JWTAuthentication])(decorated)
    decorated = api_view(["GET"])(decorated)
    decorated = require_GET(decorated)
    return decorated


def _resolve_auth_outcome(status_code: int | None) -> str:
    if not isinstance(status_code, int):
        return "unknown"
    if status_code < 400:
        return "success"
    if status_code < 500:
        return "client_error"
    return "server_error"


def track_auth_metric(event_name: str):
    def decorator(view_method: Callable[..., Any]):
        @wraps(view_method)
        def wrapped(*args, **kwargs):
            request = args[1] if len(args) > 1 else kwargs.get("request")
            endpoint = str(getattr(request, "path", "unknown"))
            monitoring_service = get_monitoring_service()

            try:
                response = view_method(*args, **kwargs)
            except Exception:
                monitoring_service.record_event(
                    event_name=event_name,
                    outcome="exception",
                    endpoint=endpoint,
                )
                raise

            monitoring_service.record_event(
                event_name=event_name,
                outcome=_resolve_auth_outcome(getattr(response, "status_code", None)),
                endpoint=endpoint,
            )
            return response

        return wrapped

    return decorator
