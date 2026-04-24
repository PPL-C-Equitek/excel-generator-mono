from datetime import datetime
from typing import Callable, Iterable

from monitoring.domain.contracts import HealthCheck, MetricsRepository
from monitoring.domain.entities import AuthMetricEvent, CheckResult, RequestMetricEvent

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"

HTTP_STATUS_OK = 200
HTTP_STATUS_UNAVAILABLE = 503


class ReadinessService:
    def __init__(self, checks: Iterable[HealthCheck]):
        self._checks = list(checks)

    def run(self) -> tuple[int, dict[str, object]]:
        results = [check.run() for check in self._checks]
        status_value = self._resolve_status(results)
        http_status = self._to_http_status(status_value)
        return http_status, {
            "status": status_value,
            "checks": [result.to_dict() for result in results],
        }

    @staticmethod
    def _resolve_status(results: list[CheckResult]) -> str:
        has_non_critical_error = False
        for result in results:
            if result.ok:
                continue
            if result.is_critical:
                return STATUS_DOWN
            has_non_critical_error = True

        if has_non_critical_error:
            return STATUS_DEGRADED
        return STATUS_OK

    @staticmethod
    def _to_http_status(status_value: str) -> int:
        if status_value == STATUS_OK:
            return HTTP_STATUS_OK
        return HTTP_STATUS_UNAVAILABLE


class MonitoringService:
    def __init__(
        self,
        *,
        readiness_service: ReadinessService,
        metrics_repository: MetricsRepository,
        now: Callable[[], datetime] | None = None,
    ):
        self._readiness_service = readiness_service
        self._metrics_repository = metrics_repository
        self._now = now or datetime.utcnow

    def live(self) -> dict[str, object]:
        return {
            "status": STATUS_OK,
            "timestamp": self._iso_now(),
        }

    def readiness(self) -> tuple[int, dict[str, object]]:
        http_status, payload = self._readiness_service.run()
        payload["timestamp"] = self._iso_now()
        return http_status, payload

    def record_request(
        self,
        *,
        route: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        self._metrics_repository.record_request(
            self._build_request_event(
                route=route,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            )
        )

    def record_event(
        self,
        *,
        event_name: str,
        outcome: str,
        endpoint: str = "",
    ) -> None:
        self._metrics_repository.record_event(
            self._build_auth_metric_event(
                event_name=event_name,
                outcome=outcome,
                endpoint=endpoint,
            )
        )

    def stats(self) -> dict[str, object]:
        snapshot = self._metrics_repository.get_snapshot()
        return {
            "status": STATUS_OK,
            **snapshot.to_dict(),
        }

    def _iso_now(self) -> str:
        return self._now().isoformat()

    def _build_request_event(
        self,
        *,
        route: str,
        method: str,
        status_code: int,
        duration_ms: float,
    ) -> RequestMetricEvent:
        return RequestMetricEvent(
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            created_at=self._now(),
        )

    def _build_auth_metric_event(
        self,
        *,
        event_name: str,
        outcome: str,
        endpoint: str,
    ) -> AuthMetricEvent:
        return AuthMetricEvent(
            event_name=event_name,
            outcome=outcome,
            endpoint=endpoint,
            created_at=self._now(),
        )
