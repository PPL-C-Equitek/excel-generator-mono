import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from authentication.jwt_authentication import JWTAuthentication
from monitoring.container import get_monitoring_service
from monitoring.interfaces.http.permissions import IsMonitoringAccount

logger = logging.getLogger(__name__)

OUTCOME_SUCCESS = "success"
OUTCOME_CLIENT_ERROR = "client_error"
OUTCOME_SERVER_ERROR = "server_error"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_EXCEPTION = "exception"


def monitoring_protected_get(view_func: Callable[..., Any]):
    decorated = permission_classes([IsAuthenticated, IsMonitoringAccount])(view_func)
    decorated = authentication_classes([JWTAuthentication])(decorated)
    decorated = api_view(["GET"])(decorated)
    decorated = require_GET(decorated)
    return decorated


def _resolve_auth_outcome(status_code: int | None) -> str:
    if not isinstance(status_code, int):
        return OUTCOME_UNKNOWN
    if status_code < 400:
        return OUTCOME_SUCCESS
    if status_code < 500:
        return OUTCOME_CLIENT_ERROR
    return OUTCOME_SERVER_ERROR


def _resolve_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    if len(args) > 1:
        return args[1]
    if len(args) == 1:
        return args[0]
    return kwargs.get("request")


def _resolve_endpoint(request: Any) -> str:
    return str(getattr(request, "path", "unknown"))


def _record_auth_event(
    *,
    monitoring_service: Any,
    event_name: str,
    outcome: str,
    endpoint: str,
) -> None:
    try:
        monitoring_service.record_event(
            event_name=event_name,
            outcome=outcome,
            endpoint=endpoint,
        )
    except Exception:
        logger.exception("Failed to record auth metrics.")


def track_auth_metric(event_name: str):
    def decorator(view_method: Callable[..., Any]):
        @wraps(view_method)
        def wrapped(*args, **kwargs):
            request = _resolve_request(args=args, kwargs=kwargs)
            endpoint = _resolve_endpoint(request)
            monitoring_service = get_monitoring_service()

            try:
                response = view_method(*args, **kwargs)
            except Exception:
                _record_auth_event(
                    monitoring_service=monitoring_service,
                    event_name=event_name,
                    outcome=OUTCOME_EXCEPTION,
                    endpoint=endpoint,
                )
                raise

            outcome = _resolve_auth_outcome(getattr(response, "status_code", None))
            _record_auth_event(
                monitoring_service=monitoring_service,
                event_name=event_name,
                outcome=outcome,
                endpoint=endpoint,
            )
            return response

        return wrapped

    return decorator
