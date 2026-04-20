from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Callable

from .entities import MetricsSnapshot, RequestMetricEvent, RouteMetricSnapshot


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

    def record_request(self, event: RequestMetricEvent) -> None:
        route = (event.route or "").strip() or "unknown"
        method = (event.method or "").strip().upper() or "UNKNOWN"
        key = (route, method)
        with self._lock:
            accumulator = self._routes.get(key)
            if accumulator is None:
                accumulator = _RouteAccumulator()
                self._routes[key] = accumulator
            accumulator.register(event)

    def get_snapshot(self) -> MetricsSnapshot:
        with self._lock:
            items = list(self._routes.items())

        route_snapshots = [
            acc.to_snapshot(route=route, method=method)
            for (route, method), acc in items
        ]
        route_snapshots.sort(
            key=lambda item: (-item.total_requests, item.route, item.method)
        )

        total_requests = sum(item.total_requests for item in route_snapshots)
        total_errors = sum(item.total_errors for item in route_snapshots)
        return MetricsSnapshot(
            generated_at=self._now(),
            total_requests=total_requests,
            total_errors=total_errors,
            routes=tuple(route_snapshots),
        )

    def reset(self) -> None:
        with self._lock:
            self._routes.clear()

