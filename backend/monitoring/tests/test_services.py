from datetime import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from monitoring.entities import CheckResult, MetricsSnapshot, RouteMetricSnapshot
from monitoring.services import MonitoringService, ReadinessService


class _StaticCheck:
    def __init__(self, result: CheckResult):
        self._result = result

    def run(self) -> CheckResult:
        return self._result


class ReadinessServiceTest(SimpleTestCase):
    def test_run_returns_ok_for_all_healthy_checks(self):
        service = ReadinessService(
            checks=[
                _StaticCheck(
                    CheckResult(
                        name="db",
                        status="ok",
                        latency_ms=1,
                        is_critical=True,
                    )
                ),
                _StaticCheck(
                    CheckResult(
                        name="storage",
                        status="ok",
                        latency_ms=1,
                        is_critical=False,
                    )
                ),
            ]
        )

        http_status, payload = service.run()
        self.assertEqual(http_status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["checks"]), 2)

    def test_run_returns_down_when_critical_check_fails(self):
        service = ReadinessService(
            checks=[
                _StaticCheck(
                    CheckResult(
                        name="db",
                        status="error",
                        latency_ms=1,
                        is_critical=True,
                        message="down",
                    )
                ),
            ]
        )

        http_status, payload = service.run()
        self.assertEqual(http_status, 503)
        self.assertEqual(payload["status"], "down")

    def test_run_returns_degraded_when_only_non_critical_checks_fail(self):
        service = ReadinessService(
            checks=[
                _StaticCheck(
                    CheckResult(
                        name="openai",
                        status="error",
                        latency_ms=1,
                        is_critical=False,
                        message="missing key",
                    )
                ),
            ]
        )

        http_status, payload = service.run()
        self.assertEqual(http_status, 503)
        self.assertEqual(payload["status"], "degraded")

    def test_run_with_no_checks_is_ok(self):
        service = ReadinessService(checks=[])

        http_status, payload = service.run()
        self.assertEqual(http_status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"], [])


class _RepositoryDouble:
    def __init__(self):
        self.recorded = []
        self.snapshot = MetricsSnapshot(
            generated_at=datetime(2026, 4, 20, 10, 0, 0),
            total_requests=3,
            total_errors=1,
            routes=(
                RouteMetricSnapshot(
                    route="/upload",
                    method="POST",
                    total_requests=3,
                    total_errors=1,
                    avg_latency_ms=100.0,
                    max_latency_ms=150.0,
                ),
            ),
        )

    def record_request(self, event):
        self.recorded.append(event)

    def get_snapshot(self):
        return self.snapshot


class MonitoringServiceTest(SimpleTestCase):
    def setUp(self):
        self.repo = _RepositoryDouble()
        self.readiness = SimpleNamespace(
            run=lambda: (
                503,
                {"status": "down", "checks": [{"name": "db", "status": "error"}]},
            )
        )
        self.now = lambda: datetime(2026, 4, 20, 10, 5, 0)
        self.service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=self.repo,
            now=self.now,
        )

    def test_live_returns_status_and_timestamp(self):
        payload = self.service.live()

        self.assertEqual(
            payload,
            {
                "status": "ok",
                "timestamp": "2026-04-20T10:05:00",
            },
        )

    def test_readiness_appends_timestamp(self):
        http_status, payload = self.service.readiness()

        self.assertEqual(http_status, 503)
        self.assertEqual(payload["status"], "down")
        self.assertEqual(payload["timestamp"], "2026-04-20T10:05:00")

    def test_record_request_sends_event_to_repository(self):
        self.service.record_request(
            route="/upload",
            method="POST",
            status_code=200,
            duration_ms=12.5,
        )

        self.assertEqual(len(self.repo.recorded), 1)
        event = self.repo.recorded[0]
        self.assertEqual(event.route, "/upload")
        self.assertEqual(event.method, "POST")
        self.assertEqual(event.status_code, 200)
        self.assertEqual(event.duration_ms, 12.5)
        self.assertEqual(event.created_at, datetime(2026, 4, 20, 10, 5, 0))

    def test_stats_maps_snapshot_payload(self):
        payload = self.service.stats()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["generated_at"], "2026-04-20T10:00:00")
        self.assertEqual(payload["totals"]["requests"], 3)
        self.assertEqual(payload["totals"]["errors"], 1)
        self.assertEqual(payload["routes"][0]["route"], "/upload")

