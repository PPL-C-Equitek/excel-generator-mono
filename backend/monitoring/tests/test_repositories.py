from datetime import datetime

from django.test import SimpleTestCase

from monitoring.entities import RequestMetricEvent
from monitoring.repositories import InMemoryMetricsRepository, _RouteAccumulator


class RouteAccumulatorTest(SimpleTestCase):
    def test_to_snapshot_uses_zero_average_when_no_requests(self):
        accumulator = _RouteAccumulator()
        snapshot = accumulator.to_snapshot(route="/health", method="GET")

        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.avg_latency_ms, 0.0)
        self.assertEqual(snapshot.max_latency_ms, 0.0)


class InMemoryMetricsRepositoryTest(SimpleTestCase):
    def setUp(self):
        self.repo = InMemoryMetricsRepository(now=lambda: datetime(2026, 4, 20, 12, 0, 0))

    def _event(
        self,
        *,
        route="/upload",
        method="POST",
        status_code=200,
        duration_ms=120.0,
    ):
        return RequestMetricEvent(
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            created_at=datetime(2026, 4, 20, 11, 59, 0),
        )

    def test_get_snapshot_returns_empty_totals_when_no_data(self):
        snapshot = self.repo.get_snapshot()

        self.assertEqual(snapshot.generated_at, datetime(2026, 4, 20, 12, 0, 0))
        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.total_errors, 0)
        self.assertEqual(snapshot.routes, ())

    def test_record_request_aggregates_totals_and_errors(self):
        self.repo.record_request(self._event(status_code=200, duration_ms=100.0))
        self.repo.record_request(self._event(status_code=502, duration_ms=300.0))

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 2)
        self.assertEqual(snapshot.total_errors, 1)
        self.assertEqual(len(snapshot.routes), 1)
        route = snapshot.routes[0]
        self.assertEqual(route.route, "/upload")
        self.assertEqual(route.method, "POST")
        self.assertEqual(route.total_requests, 2)
        self.assertEqual(route.total_errors, 1)
        self.assertEqual(route.avg_latency_ms, 200.0)
        self.assertEqual(route.max_latency_ms, 300.0)

    def test_record_request_normalizes_empty_route_and_method(self):
        self.repo.record_request(self._event(route=" ", method=" ", duration_ms=10.0))

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.routes[0].route, "unknown")
        self.assertEqual(snapshot.routes[0].method, "UNKNOWN")

    def test_record_request_clamps_negative_duration_to_zero(self):
        self.repo.record_request(self._event(duration_ms=-10.0))

        route = self.repo.get_snapshot().routes[0]
        self.assertEqual(route.avg_latency_ms, 0.0)
        self.assertEqual(route.max_latency_ms, 0.0)

    def test_get_snapshot_sorts_by_total_requests_then_route_method(self):
        self.repo.record_request(self._event(route="/b", method="GET", duration_ms=1.0))
        self.repo.record_request(self._event(route="/a", method="GET", duration_ms=1.0))
        self.repo.record_request(self._event(route="/b", method="GET", duration_ms=1.0))

        routes = self.repo.get_snapshot().routes
        self.assertEqual([item.route for item in routes], ["/b", "/a"])

    def test_reset_clears_accumulated_metrics(self):
        self.repo.record_request(self._event())
        self.repo.reset()

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.routes, ())

