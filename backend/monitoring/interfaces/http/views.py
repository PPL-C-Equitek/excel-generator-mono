import json
import logging
from time import sleep

from django.conf import settings
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from api.decorators import rate_limit
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from authentication.jwt_authentication import JWTAuthentication
from monitoring.application.access_policy import MonitoringAccessPolicy
from monitoring.container import get_monitoring_service
from monitoring.interfaces.http.decorators import monitoring_protected_get

STREAM_EVENT_NAME = "stats"
MONITORING_RATE_LIMIT_REQUESTS_PER_MINUTE = 120

logger = logging.getLogger(__name__)


def _resolve_stream_interval_seconds(raw_value: object) -> float:
    fallback = float(getattr(settings, "MONITORING_STREAM_INTERVAL_SECONDS", 2.0))
    try:
        parsed = float(raw_value)
        if parsed <= 0:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        return fallback


def _resolve_stream_max_events(raw_value: object) -> int | None:
    try:
        parsed = int(raw_value)
        if parsed <= 0:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _resolve_monitoring_rate_limit_identity(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        user_id = getattr(user, "id", None)
        if user_id is None:
            user_id = getattr(user, "pk", None)
        return f"user:{user_id if user_id is not None else 'unknown'}"

    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{remote_addr}"


def _monitoring_rate_limit():
    try:
        max_requests = int(
            getattr(settings, "MONITORING_RATE_LIMIT_MAX_REQUESTS", MONITORING_RATE_LIMIT_REQUESTS_PER_MINUTE)
        )
        if max_requests <= 0:
            max_requests = MONITORING_RATE_LIMIT_REQUESTS_PER_MINUTE
    except (TypeError, ValueError):
        logger.warning("Invalid MONITORING_RATE_LIMIT_MAX_REQUESTS configured; using default.")
        max_requests = MONITORING_RATE_LIMIT_REQUESTS_PER_MINUTE

    per = str(getattr(settings, "MONITORING_RATE_LIMIT_PER", "minute")).strip().lower()
    if per not in {"second", "seconds", "minute", "minutes"}:
        logger.warning("Invalid MONITORING_RATE_LIMIT_PER configured; using default minute.")
        per = "minute"

    return rate_limit(
        max_requests=max_requests,
        per=per,
        key_func=_resolve_monitoring_rate_limit_identity,
    )


def _stats_stream(*, service, interval_seconds: float, max_events: int | None):
    emitted = 0
    while True:
        payload = service.stats()
        serialized_payload = json.dumps(payload, separators=(",", ":"))
        yield f"event: {STREAM_EVENT_NAME}\ndata: {serialized_payload}\n\n"
        emitted += 1
        if max_events is not None and emitted >= max_events:
            return
        sleep(interval_seconds)


@require_GET
@api_view(["GET"])
@_monitoring_rate_limit()
def live(request):
    payload = get_monitoring_service().live()
    return Response(payload, status=status.HTTP_200_OK)


@monitoring_protected_get
@_monitoring_rate_limit()
def ready(request):
    http_status, payload = get_monitoring_service().readiness()
    return Response(payload, status=http_status)


@monitoring_protected_get
@_monitoring_rate_limit()
def stats(request):
    payload = get_monitoring_service().stats()
    return Response(payload, status=status.HTTP_200_OK)


@require_GET
@api_view(["GET"])
@_monitoring_rate_limit()
def snapshot(request):
    decision = MonitoringAccessPolicy().evaluate(getattr(request, "user", None))
    decision_payload = decision.to_dict()

    if not decision.allowed:
        return Response(
            {
                "access": decision_payload,
                "ready": None,
                "stats": None,
            },
            status=status.HTTP_200_OK,
        )

    service = get_monitoring_service()
    _, ready_payload = service.readiness()
    return Response(
        {
            "access": decision_payload,
            "ready": ready_payload,
            "stats": service.stats(),
        },
        status=status.HTTP_200_OK,
    )


@require_GET
@monitoring_protected_get
@_monitoring_rate_limit()
def stream(request):
    service = get_monitoring_service()
    interval_seconds = _resolve_stream_interval_seconds(
        request.query_params.get("interval_seconds")
    )
    max_events = _resolve_stream_max_events(request.query_params.get("max_events"))
    response = StreamingHttpResponse(
        _stats_stream(
            service=service,
            interval_seconds=interval_seconds,
            max_events=max_events,
        ),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_GET
@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@_monitoring_rate_limit()
def access(request):
    decision = MonitoringAccessPolicy().evaluate(getattr(request, "user", None))
    return Response(
        decision.to_dict(),
        status=status.HTTP_200_OK,
    )
