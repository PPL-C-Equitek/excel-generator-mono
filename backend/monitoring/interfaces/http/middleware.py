import logging
from time import perf_counter

from monitoring.container import get_monitoring_service

logger = logging.getLogger(__name__)

DEFAULT_ERROR_STATUS = 500
DEFAULT_UNKNOWN_METHOD = "UNKNOWN"
DEFAULT_UNKNOWN_PATH = "unknown"
MONITORING_ROUTE_PREFIX = "monitoring/"


class MonitoringRequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        status_code = DEFAULT_ERROR_STATUS
        try:
            response = self.get_response(request)
            status_code = self._resolve_status_code(response)
            return response
        finally:
            self._record_request_metrics(
                request=request,
                status_code=status_code,
                duration_ms=self._elapsed_ms(started),
            )

    def _record_request_metrics(self, *, request, status_code: int, duration_ms: float) -> None:
        route = self._resolve_route(request)
        if self._is_monitoring_route(route):
            return
        method = self._resolve_method(request)
        try:
            get_monitoring_service().record_request(
                route=route,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.exception("Failed to record request metrics.")

    @staticmethod
    def _resolve_route(request) -> str:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match and getattr(resolver_match, "route", None):
            return str(resolver_match.route)
        return str(getattr(request, "path", DEFAULT_UNKNOWN_PATH))

    @staticmethod
    def _resolve_method(request) -> str:
        return str(getattr(request, "method", DEFAULT_UNKNOWN_METHOD))

    @staticmethod
    def _is_monitoring_route(route: str) -> bool:
        normalized_route = route.strip().lstrip("/").lower()
        return normalized_route.startswith(MONITORING_ROUTE_PREFIX)

    @staticmethod
    def _resolve_status_code(response) -> int:
        return int(getattr(response, "status_code", DEFAULT_ERROR_STATUS) or DEFAULT_ERROR_STATUS)

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (perf_counter() - started) * 1000
