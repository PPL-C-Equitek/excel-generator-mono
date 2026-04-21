from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    latency_ms: int
    is_critical: bool = True
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "is_critical": self.is_critical,
        }
        if self.message:
            payload["message"] = self.message
        return payload


@dataclass(frozen=True)
class RequestMetricEvent:
    route: str
    method: str
    status_code: int
    duration_ms: float
    created_at: datetime


@dataclass(frozen=True)
class AuthMetricEvent:
    event_name: str
    outcome: str
    endpoint: str
    created_at: datetime


@dataclass(frozen=True)
class RouteMetricSnapshot:
    route: str
    method: str
    total_requests: int
    total_errors: int
    avg_latency_ms: float
    max_latency_ms: float

    @property
    def error_rate(self) -> float:
        if self.total_requests <= 0:
            return 0.0
        return self.total_errors / self.total_requests

    def to_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "method": self.method,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "max_latency_ms": self.max_latency_ms,
        }


@dataclass(frozen=True)
class EventMetricSnapshot:
    event_name: str
    outcome: str
    count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "event_name": self.event_name,
            "outcome": self.outcome,
            "count": self.count,
        }


@dataclass(frozen=True)
class MetricsSnapshot:
    generated_at: datetime
    total_requests: int
    total_errors: int
    routes: tuple[RouteMetricSnapshot, ...]
    events: tuple[EventMetricSnapshot, ...] = ()

    @property
    def error_rate(self) -> float:
        if self.total_requests <= 0:
            return 0.0
        return self.total_errors / self.total_requests

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "totals": {
                "requests": self.total_requests,
                "errors": self.total_errors,
                "error_rate": self.error_rate,
            },
            "routes": [route.to_dict() for route in self.routes],
            "events": self._events_to_dict(),
        }

    def _events_to_dict(self) -> dict[str, dict[str, int]]:
        events_payload: dict[str, dict[str, int]] = {}
        for event in self.events:
            per_event = events_payload.setdefault(event.event_name, {})
            per_event[event.outcome] = event.count
        return events_payload
