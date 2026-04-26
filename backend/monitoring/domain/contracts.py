from typing import Protocol

from .entities import AuthMetricEvent, CheckResult, MetricsSnapshot, RequestMetricEvent


class HealthCheck(Protocol):
    name: str
    is_critical: bool

    def run(self) -> CheckResult:
        ...


class MetricsRepository(Protocol):
    def record_request(self, event: RequestMetricEvent) -> None:
        ...

    def record_event(self, event: AuthMetricEvent) -> None:
        ...

    def get_snapshot(self) -> MetricsSnapshot:
        ...


class MonitoringAlertNotifier(Protocol):
    def notify(self, *, event_name: str, payload: dict[str, object]) -> None:
        ...
