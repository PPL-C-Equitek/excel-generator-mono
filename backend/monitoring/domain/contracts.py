from typing import Protocol

from .entities import CheckResult, MetricsSnapshot, RequestMetricEvent


class HealthCheck(Protocol):
    name: str
    is_critical: bool

    def run(self) -> CheckResult:
        ...


class MetricsRepository(Protocol):
    def record_request(self, event: RequestMetricEvent) -> None:
        ...

    def get_snapshot(self) -> MetricsSnapshot:
        ...

