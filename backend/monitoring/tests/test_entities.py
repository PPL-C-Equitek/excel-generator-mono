from datetime import datetime

from django.test import SimpleTestCase

from monitoring.entities import CheckResult, MetricsSnapshot, RouteMetricSnapshot


class CheckResultEntityTest(SimpleTestCase):
    def test_to_dict_without_message(self):
        result = CheckResult(name="db", status="ok", latency_ms=12, is_critical=True)

        self.assertTrue(result.ok)
        self.assertEqual(
            result.to_dict(),
            {
                "name": "db",
                "status": "ok",
                "latency_ms": 12,
                "is_critical": True,
            },
        )

    def test_to_dict_with_message(self):
        result = CheckResult(
            name="storage",
            status="error",
            latency_ms=7,
            is_critical=False,
            message="disk unavailable",
        )

        self.assertFalse(result.ok)
        self.assertEqual(
            result.to_dict(),
            {
                "name": "storage",
                "status": "error",
                "latency_ms": 7,
                "is_critical": False,
                "message": "disk unavailable",
            },
        )


class RouteMetricSnapshotEntityTest(SimpleTestCase):
    def test_error_rate_and_to_dict(self):
        route = RouteMetricSnapshot(
            route="/upload",
            method="POST",
            total_requests=5,
            total_errors=2,
            avg_latency_ms=250.5,
            max_latency_ms=700.0,
        )

        self.assertEqual(route.error_rate, 0.4)
        self.assertEqual(
            route.to_dict(),
            {
                "route": "/upload",
                "method": "POST",
                "total_requests": 5,
                "total_errors": 2,
                "error_rate": 0.4,
                "avg_latency_ms": 250.5,
                "max_latency_ms": 700.0,
            },
        )

    def test_error_rate_zero_when_no_requests(self):
        route = RouteMetricSnapshot(
            route="/upload",
            method="POST",
            total_requests=0,
            total_errors=0,
            avg_latency_ms=0.0,
            max_latency_ms=0.0,
        )

        self.assertEqual(route.error_rate, 0.0)


class MetricsSnapshotEntityTest(SimpleTestCase):
    def test_to_dict_with_routes(self):
        snapshot = MetricsSnapshot(
            generated_at=datetime(2026, 4, 20, 10, 0, 0),
            total_requests=10,
            total_errors=3,
            routes=(
                RouteMetricSnapshot(
                    route="/upload",
                    method="POST",
                    total_requests=10,
                    total_errors=3,
                    avg_latency_ms=200.0,
                    max_latency_ms=500.0,
                ),
            ),
        )

        self.assertEqual(snapshot.error_rate, 0.3)
        self.assertEqual(
            snapshot.to_dict(),
            {
                "generated_at": "2026-04-20T10:00:00",
                "totals": {
                    "requests": 10,
                    "errors": 3,
                    "error_rate": 0.3,
                },
                "routes": [
                    {
                        "route": "/upload",
                        "method": "POST",
                        "total_requests": 10,
                        "total_errors": 3,
                        "error_rate": 0.3,
                        "avg_latency_ms": 200.0,
                        "max_latency_ms": 500.0,
                    }
                ],
            },
        )

    def test_error_rate_zero_when_no_requests(self):
        snapshot = MetricsSnapshot(
            generated_at=datetime(2026, 4, 20, 10, 0, 0),
            total_requests=0,
            total_errors=0,
            routes=(),
        )

        self.assertEqual(snapshot.error_rate, 0.0)

