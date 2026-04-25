from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from monitoring.entities import EventMetricSnapshot, CheckResult, MetricsSnapshot, RouteMetricSnapshot
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
        self.get_snapshot_calls = 0
        self.recorded = []
        self.recorded_events = []
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
            events=(
                EventMetricSnapshot(
                    event_name="login",
                    outcome="success",
                    count=2,
                ),
            ),
        )

    def record_request(self, event):
        self.recorded.append(event)

    def record_event(self, event):
        self.recorded_events.append(event)

    def get_snapshot(self):
        self.get_snapshot_calls += 1
        return self.snapshot


class _ReadinessSequenceDouble:
    def __init__(self, responses):
        self._responses = iter(responses)

    def run(self):
        return next(self._responses)


class _Clock:
    def __init__(self, now: datetime):
        self.current = now

    def __call__(self) -> datetime:
        return self.current

    def tick(self, *, seconds: int) -> None:
        self.current = self.current + timedelta(seconds=seconds)


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

    def test_readiness_ok_status_resets_last_readiness_status_and_skips_notifier(self):
        notifier = Mock()
        readiness = _ReadinessSequenceDouble([(200, {"status": "ok", "checks": []})])
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=notifier,
            now=self.now,
        )

        status_code, payload = service.readiness()

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ok")
        notifier.notify.assert_not_called()
        self.assertEqual(service._last_readiness_status, "ok")

    def test_readiness_notifies_webhook_for_non_ok_status(self):
        notifier = Mock()
        readiness = _ReadinessSequenceDouble(
            [
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
            ]
        )
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=notifier,
            readiness_alert_cooldown_seconds=10,
            now=lambda: datetime(2026, 4, 20, 10, 5, 0),
        )

        first_status, first_payload = service.readiness()

        self.assertEqual(first_status, 503)
        self.assertEqual(first_payload["status"], "down")
        notifier.notify.assert_called_once()
        called_payload = notifier.notify.call_args.kwargs["payload"]
        self.assertEqual(called_payload["status"], "down")
        self.assertEqual(called_payload["http_status"], 503)
        self.assertEqual(called_payload["checks"], [{"name": "db", "status": "error"}])

    def test_readiness_avoids_repeating_notifications_within_cooldown(self):
        notifier = Mock()
        readiness = _ReadinessSequenceDouble(
            [
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
            ]
        )
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=notifier,
            readiness_alert_cooldown_seconds=60,
            now=lambda: datetime(2026, 4, 20, 10, 5, 0),
        )

        service.readiness()
        service.readiness()
        service.readiness()

        notifier.notify.assert_called_once()

    def test_readiness_notifies_when_status_changes(self):
        notifier = Mock()
        readiness = _ReadinessSequenceDouble(
            [
                (503, {"status": "degraded", "checks": [{"name": "openai", "status": "error"}]}),
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
            ]
        )
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=notifier,
            readiness_alert_cooldown_seconds=300,
            now=lambda: datetime(2026, 4, 20, 10, 5, 0),
        )

        service.readiness()
        service.readiness()

        self.assertEqual(notifier.notify.call_count, 2)

    def test_readiness_does_not_raise_when_notifier_fails(self):
        readiness = _ReadinessSequenceDouble(
            [
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
            ]
        )
        failing_notifier = Mock()
        failing_notifier.notify.side_effect = RuntimeError("discord down")
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=failing_notifier,
            now=lambda: datetime(2026, 4, 20, 10, 5, 0),
        )

        http_status, payload = service.readiness()

        self.assertEqual(http_status, 503)
        self.assertEqual(payload["status"], "down")
        failing_notifier.notify.assert_called_once()

    def test_readiness_sets_alert_state_even_if_notifier_fails(self):
        readiness = _ReadinessSequenceDouble(
            [
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
                (503, {"status": "down", "checks": [{"name": "db", "status": "error"}]}),
            ]
        )
        failing_notifier = Mock()
        failing_notifier.notify.side_effect = RuntimeError("discord down")
        now = datetime(2026, 4, 20, 10, 5, 0)
        service = MonitoringService(
            readiness_service=readiness,
            metrics_repository=self.repo,
            alert_notifier=failing_notifier,
            readiness_alert_cooldown_seconds=60,
            now=lambda: now,
        )

        service.readiness()
        service.readiness()

        self.assertEqual(failing_notifier.notify.call_count, 1)
        self.assertEqual(service._last_readiness_status, "down")
        self.assertEqual(service._last_readiness_alert_time, now)

    def test_should_send_readiness_alert_without_previous_alert_time(self):
        service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=self.repo,
            alert_notifier=Mock(),
            now=self.now,
        )
        service._last_readiness_status = "down"
        service._last_readiness_alert_time = None

        self.assertTrue(
            service._should_send_readiness_alert(
                now=datetime(2026, 4, 20, 10, 5, 0),
                status="down",
            )
        )

    def test_stats_uses_short_lived_cache(self):
        clock = _Clock(datetime(2026, 4, 20, 10, 5, 0))
        service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=self.repo,
            now=clock,
            stats_cache_ttl_seconds=5,
        )

        service.stats()
        clock.tick(seconds=4)
        service.stats()
        clock.tick(seconds=2)
        service.stats()

        self.assertEqual(self.repo.get_snapshot_calls, 2)

    def test_stats_skips_cache_when_ttl_is_zero(self):
        repo = _RepositoryDouble()
        service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=repo,
            now=lambda: datetime(2026, 4, 20, 10, 5, 0),
            stats_cache_ttl_seconds=0,
        )

        service.stats()
        service.stats()

        self.assertEqual(repo.get_snapshot_calls, 2)

    def test_stats_cache_invalidated_after_record_request(self):
        clock = _Clock(datetime(2026, 4, 20, 10, 5, 0))
        service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=self.repo,
            now=clock,
            stats_cache_ttl_seconds=300,
        )

        service.stats()
        service.record_request(
            route="/upload",
            method="POST",
            status_code=200,
            duration_ms=10.0,
        )
        service.stats()

        self.assertEqual(self.repo.get_snapshot_calls, 2)

    def test_stats_cache_invalidated_after_record_event(self):
        clock = _Clock(datetime(2026, 4, 20, 10, 5, 0))
        service = MonitoringService(
            readiness_service=self.readiness,
            metrics_repository=self.repo,
            now=clock,
            stats_cache_ttl_seconds=300,
        )

        service.stats()
        service.record_event(
            event_name="login",
            outcome="success",
            endpoint="/auth/login/",
        )
        service.stats()

        self.assertEqual(self.repo.get_snapshot_calls, 2)

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

    def test_record_event_sends_auth_metric_event_to_repository(self):
        self.service.record_event(
            event_name="login",
            outcome="success",
            endpoint="/auth/login/",
        )

        self.assertEqual(len(self.repo.recorded_events), 1)
        event = self.repo.recorded_events[0]
        self.assertEqual(event.event_name, "login")
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.endpoint, "/auth/login/")
        self.assertEqual(event.created_at, datetime(2026, 4, 20, 10, 5, 0))

    def test_stats_maps_snapshot_payload(self):
        payload = self.service.stats()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["generated_at"], "2026-04-20T10:00:00")
        self.assertEqual(payload["totals"]["requests"], 3)
        self.assertEqual(payload["totals"]["errors"], 1)
        self.assertEqual(payload["routes"][0]["route"], "/upload")
        self.assertEqual(payload["events"]["login"]["success"], 2)
