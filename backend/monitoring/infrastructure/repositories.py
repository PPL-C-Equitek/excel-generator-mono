from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Callable

from monitoring.domain.entities import (
    AuthMetricEvent,
    EventMetricSnapshot,
    MetricsSnapshot,
    RequestMetricEvent,
    RouteMetricSnapshot,
)


@dataclass
class _RouteAccumulator:
    total_requests: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    def register(self, event: RequestMetricEvent) -> None:
        duration_ms = max(0.0, float(event.duration_ms))
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        self.max_latency_ms = max(self.max_latency_ms, duration_ms)
        if event.status_code >= 500:
            self.total_errors += 1

    def to_snapshot(self, route: str, method: str) -> RouteMetricSnapshot:
        avg_latency = 0.0
        if self.total_requests > 0:
            avg_latency = self.total_latency_ms / self.total_requests
        return RouteMetricSnapshot(
            route=route,
            method=method,
            total_requests=self.total_requests,
            total_errors=self.total_errors,
            avg_latency_ms=avg_latency,
            max_latency_ms=self.max_latency_ms,
        )


class InMemoryMetricsRepository:
    def __init__(self, *, now: Callable[[], datetime] | None = None):
        self._now = now or datetime.utcnow
        self._lock = Lock()
        self._routes: dict[tuple[str, str], _RouteAccumulator] = {}
        self._events: dict[tuple[str, str], int] = {}

    def record_request(self, event: RequestMetricEvent) -> None:
        key = self._route_key_from_event(event)
        with self._lock:
            accumulator = self._routes.get(key)
            if accumulator is None:
                accumulator = _RouteAccumulator()
                self._routes[key] = accumulator
            accumulator.register(event)

    def record_event(self, event: AuthMetricEvent) -> None:
        key = self._event_key_from_event(event)
        with self._lock:
            self._events[key] = self._events.get(key, 0) + 1

    def get_snapshot(self) -> MetricsSnapshot:
        with self._lock:
            items = list(self._routes.items())
            event_items = list(self._events.items())

        route_snapshots = self._build_route_snapshots(items)
        event_snapshots = self._build_event_snapshots(event_items)

        total_requests = sum(item.total_requests for item in route_snapshots)
        total_errors = sum(item.total_errors for item in route_snapshots)
        return MetricsSnapshot(
            generated_at=self._now(),
            total_requests=total_requests,
            total_errors=total_errors,
            routes=tuple(route_snapshots),
            events=tuple(event_snapshots),
        )

    def reset(self) -> None:
        with self._lock:
            self._routes.clear()
            self._events.clear()

    @staticmethod
    def _normalize_text(
        value: str | None,
        *,
        default: str,
        transform: Callable[[str], str] | None = None,
    ) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return default
        if transform is None:
            return normalized
        return transform(normalized)

    @classmethod
    def _route_key_from_event(cls, event: RequestMetricEvent) -> tuple[str, str]:
        return (
            cls._normalize_text(event.route, default="unknown"),
            cls._normalize_text(event.method, default="UNKNOWN", transform=str.upper),
        )

    @classmethod
    def _event_key_from_event(cls, event: AuthMetricEvent) -> tuple[str, str]:
        return (
            cls._normalize_text(event.event_name, default="unknown", transform=str.lower),
            cls._normalize_text(event.outcome, default="unknown", transform=str.lower),
        )

    @staticmethod
    def _build_route_snapshots(
        items: list[tuple[tuple[str, str], _RouteAccumulator]]
    ) -> list[RouteMetricSnapshot]:
        route_snapshots = [
            accumulator.to_snapshot(route=route, method=method)
            for (route, method), accumulator in items
        ]
        route_snapshots.sort(
            key=lambda item: (-item.total_requests, item.route, item.method)
        )
        return route_snapshots

    @staticmethod
    def _build_event_snapshots(
        event_items: list[tuple[tuple[str, str], int]]
    ) -> list[EventMetricSnapshot]:
        event_snapshots = [
            EventMetricSnapshot(event_name=event_name, outcome=outcome, count=count)
            for (event_name, outcome), count in event_items
        ]
        event_snapshots.sort(
            key=lambda item: (-item.count, item.event_name, item.outcome)
        )
        return event_snapshots
