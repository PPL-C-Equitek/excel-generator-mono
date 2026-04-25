import logging
from copy import deepcopy
from datetime import datetime
from typing import Callable, Iterable

from monitoring.domain.contracts import (
    HealthCheck,
    MonitoringAlertNotifier,
    MetricsRepository,
)
from monitoring.domain.entities import AuthMetricEvent, CheckResult, RequestMetricEvent

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"

HTTP_STATUS_OK = 200
HTTP_STATUS_UNAVAILABLE = 503
DEFAULT_READINESS_ALERT_COOLDOWN_SECONDS = 300
DEFAULT_STATS_CACHE_TTL_SECONDS = 2.0

logger = logging.getLogger(__name__)


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
        alert_notifier: MonitoringAlertNotifier | None = None,
        readiness_alert_cooldown_seconds: int = DEFAULT_READINESS_ALERT_COOLDOWN_SECONDS,
        stats_cache_ttl_seconds: float = DEFAULT_STATS_CACHE_TTL_SECONDS,
        now: Callable[[], datetime] | None = None,
    ):
        self._readiness_service = readiness_service
        self._metrics_repository = metrics_repository
        self._alert_notifier = alert_notifier
        self._readiness_alert_cooldown_seconds = readiness_alert_cooldown_seconds
        self._stats_cache_ttl_seconds = stats_cache_ttl_seconds
        self._now = now or datetime.utcnow
        self._last_readiness_status: str | None = None
        self._last_readiness_alert_time: datetime | None = None
        self._cached_stats_payload: dict[str, object] | None = None
        self._cached_stats_at: datetime | None = None

    def live(self) -> dict[str, object]:
        return {
            "status": STATUS_OK,
            "timestamp": self._iso_now(),
        }

    def readiness(self) -> tuple[int, dict[str, object]]:
        http_status, payload = self._readiness_service.run()
        payload["timestamp"] = self._iso_now()
        self._notify_if_readiness_non_ok(payload=payload, http_status=http_status)
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
        self._invalidate_stats_cache()

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
        self._invalidate_stats_cache()

    def stats(self) -> dict[str, object]:
        now = self._now()
        if self._is_stats_cache_fresh(now=now):
            return deepcopy(self._cached_stats_payload)

        snapshot = self._metrics_repository.get_snapshot()
        payload = {
            "status": STATUS_OK,
            **snapshot.to_dict(),
        }
        self._cached_stats_payload = payload
        self._cached_stats_at = now
        return deepcopy(payload)

    def _is_stats_cache_fresh(self, *, now: datetime) -> bool:
        if self._cached_stats_payload is None or self._cached_stats_at is None:
            return False
        if self._stats_cache_ttl_seconds <= 0:
            return False
        age_seconds = (now - self._cached_stats_at).total_seconds()
        return age_seconds <= self._stats_cache_ttl_seconds

    def _invalidate_stats_cache(self) -> None:
        self._cached_stats_payload = None
        self._cached_stats_at = None

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

    def _notify_if_readiness_non_ok(
        self,
        *,
        payload: dict[str, object],
        http_status: int,
    ) -> None:
        status = str(payload.get("status", ""))
        if status == STATUS_OK or self._alert_notifier is None:
            self._last_readiness_status = status
            return

        now = self._now()
        if not self._should_send_readiness_alert(now=now, status=status):
            return

        self._last_readiness_status = status
        try:
            self._alert_notifier.notify(
                event_name="monitoring.readiness",
                payload=self._build_readiness_alert_payload(
                    http_status=http_status,
                    payload=payload,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to send monitoring readiness notification for status '%s'.",
                status,
            )
            self._last_readiness_alert_time = now
            return

        self._last_readiness_alert_time = now

    def _should_send_readiness_alert(self, *, now: datetime, status: str) -> bool:
        if self._last_readiness_status != status:
            return True
        if self._last_readiness_alert_time is None:
            return True
        cooldown = self._readiness_alert_cooldown_seconds
        elapsed = (now - self._last_readiness_alert_time).total_seconds()
        return elapsed >= cooldown

    def _build_readiness_alert_payload(
        self,
        *,
        http_status: int,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return {
            "event": "monitoring.readiness",
            "status": payload.get("status", STATUS_DOWN),
            "http_status": http_status,
            "timestamp": payload.get("timestamp"),
            "checks": payload.get("checks", ()),
        }
