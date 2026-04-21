import logging
from time import perf_counter

from monitoring.container import get_monitoring_service

logger = logging.getLogger(__name__)


class MonitoringRequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            self._record_request_metrics(
                request=request,
                status_code=500,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise

        self._record_request_metrics(
            request=request,
            status_code=getattr(response, "status_code", 500) or 500,
            duration_ms=(perf_counter() - started) * 1000,
        )
        return response

    def _record_request_metrics(self, *, request, status_code: int, duration_ms: float) -> None:
        route = self._resolve_route(request)
        method = getattr(request, "method", "UNKNOWN")
        try:
            get_monitoring_service().record_request(
                route=route,
                method=method,
                status_code=int(status_code),
                duration_ms=duration_ms,
            )
        except Exception:
            logger.exception("Failed to record request metrics.")

    @staticmethod
    def _resolve_route(request) -> str:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match and getattr(resolver_match, "route", None):
            return str(resolver_match.route)
        return str(getattr(request, "path", "unknown"))

