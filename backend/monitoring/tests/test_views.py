from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from authentication.models import User
from monitoring.models import MonitoringAccount
from monitoring.interfaces.http.views import (
    _resolve_stream_interval_seconds,
    _resolve_stream_max_events,
    _stats_stream,
    _resolve_monitoring_rate_limit_identity,
    _monitoring_rate_limit,
)


@override_settings(ROOT_URLCONF="monitoring.urls")
class MonitoringViewsTest(APITestCase):
    def test_resolve_monitoring_rate_limit_identity_prefers_user_id(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_authenticated=True,
                id=42,
                pk=11,
            ),
            META={},
        )

        self.assertEqual(
            _resolve_monitoring_rate_limit_identity(request),
            "user:42",
        )

    def test_resolve_monitoring_rate_limit_identity_falls_back_to_pk_when_id_is_missing(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_authenticated=True,
                id=None,
                pk=99,
            ),
            META={},
        )

        self.assertEqual(
            _resolve_monitoring_rate_limit_identity(request),
            "user:99",
        )

    def test_resolve_monitoring_rate_limit_identity_falls_back_to_forwarded_ip_for_anonymous_request(self):
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            META={
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.10, 203.0.113.1",
            },
        )

        self.assertEqual(
            _resolve_monitoring_rate_limit_identity(request),
            "ip:198.51.100.10",
        )

    def test_resolve_monitoring_rate_limit_identity_falls_back_to_remote_addr_without_forwarded_ip(self):
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            META={"REMOTE_ADDR": "10.0.0.1"},
        )

        self.assertEqual(
            _resolve_monitoring_rate_limit_identity(request),
            "ip:10.0.0.1",
        )

    @override_settings(
        MONITORING_RATE_LIMIT_MAX_REQUESTS="0",
        MONITORING_RATE_LIMIT_PER="invalid",
    )
    @patch("monitoring.interfaces.http.views.rate_limit")
    def test_monitoring_rate_limit_defaults_for_invalid_config(self, mocked_rate_limit):
        _monitoring_rate_limit()

        mocked_rate_limit.assert_called_once_with(
            max_requests=120,
            per="minute",
            key_func=_resolve_monitoring_rate_limit_identity,
        )

    @override_settings(
        MONITORING_RATE_LIMIT_MAX_REQUESTS="abc",
        MONITORING_RATE_LIMIT_PER="seconds",
    )
    @patch("monitoring.interfaces.http.views.rate_limit")
    def test_monitoring_rate_limit_uses_validized_per_when_max_invalid(self, mocked_rate_limit):
        _monitoring_rate_limit()

        mocked_rate_limit.assert_called_once_with(
            max_requests=120,
            per="seconds",
            key_func=_resolve_monitoring_rate_limit_identity,
        )

    def test_resolve_stream_interval_seconds_handles_invalid_value(self):
        self.assertEqual(_resolve_stream_interval_seconds("invalid"), 2.0)

    @override_settings(MONITORING_STREAM_INTERVAL_SECONDS=7.5)
    def test_resolve_stream_interval_seconds_uses_fallback_for_non_positive_value(self):
        self.assertEqual(_resolve_stream_interval_seconds("0"), 7.5)

    def test_resolve_stream_interval_seconds_uses_positive_value(self):
        self.assertEqual(_resolve_stream_interval_seconds("2.5"), 2.5)

    def test_resolve_stream_max_events_returns_none_for_invalid_value(self):
        self.assertIsNone(_resolve_stream_max_events("invalid"))

    def test_resolve_stream_max_events_returns_none_for_zero_or_negative(self):
        self.assertIsNone(_resolve_stream_max_events("0"))
        self.assertIsNone(_resolve_stream_max_events("-1"))

    def test_resolve_stream_max_events_returns_positive_int(self):
        self.assertEqual(_resolve_stream_max_events("4"), 4)

    @patch("monitoring.interfaces.http.views.sleep", return_value=None)
    def test_stats_stream_yields_expected_event_count(self, mocked_sleep):
        service = Mock()
        service.stats.return_value = {
            "status": "ok",
            "generated_at": "2026-04-20T10:00:00",
            "totals": {"requests": 1, "errors": 0, "error_rate": 0.0},
            "routes": [],
        }

        stream = _stats_stream(
            service=service,
            interval_seconds=1.5,
            max_events=2,
        )
        first_payload = next(stream)
        second_payload = next(stream)
        self.assertIn("event: stats", first_payload)
        self.assertIn("event: stats", second_payload)
        mocked_sleep.assert_called_once_with(1.5)
        self.assertEqual(service.stats.call_count, 2)

        with self.assertRaises(StopIteration):
            next(stream)

    @patch("monitoring.interfaces.http.views.sleep", return_value=None)
    def test_stats_stream_prefers_stats_json_when_service_supports_it(self, mocked_sleep):
        class _ServiceWithStatsJson:
            def __init__(self):
                self.stats_json_calls = 0
                self.stats_calls = 0

            def stats_json(self):
                self.stats_json_calls += 1
                return '{"status":"ok"}'

            def stats(self):
                self.stats_calls += 1
                return {"status": "ok"}

        service = _ServiceWithStatsJson()

        stream = _stats_stream(
            service=service,
            interval_seconds=1.0,
            max_events=1,
        )
        first_payload = next(stream)

        self.assertIn('data: {"status":"ok"}', first_payload)
        self.assertEqual(service.stats_json_calls, 1)
        self.assertEqual(service.stats_calls, 0)
        mocked_sleep.assert_not_called()

        with self.assertRaises(StopIteration):
            next(stream)

    def test_stream_endpoint_with_invalid_query_values_still_returns_stream(self):
        user = User.objects.create_user(
            email="stream-invalid-query@example.com",
            name="Stream Invalid Query",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/stream/?interval_seconds=0&max_events=0")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])
    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_live_endpoint_returns_payload_for_unauthenticated_user(
        self,
        mocked_get_service,
    ):
        service = Mock()
        service.live.return_value = {
            "status": "ok",
            "timestamp": "2026-04-20T10:00:00",
        }
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "status": "ok",
                "timestamp": "2026-04-20T10:00:00",
            },
        )
        service.live.assert_called_once()
        self.assertIn("X-RateLimit-Limit", response)
        self.assertIn("X-RateLimit-Remaining", response)

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_ready_endpoint_returns_401_for_unauthenticated_user(
        self,
        mocked_get_service,
    ):
        response = self.client.get("/monitoring/ready/")

        self.assertEqual(response.status_code, 401)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_ready_endpoint_returns_403_for_verified_user_without_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="verified-no-monitoring@example.com",
            name="Verified No Monitoring",
            status="verified",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/ready/")

        self.assertEqual(response.status_code, 403)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_ready_endpoint_returns_403_for_unverified_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="unverified-monitoring@example.com",
            name="Unverified Monitoring",
            status="unverified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/ready/")

        self.assertEqual(response.status_code, 403)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_ready_endpoint_returns_503_for_authorized_monitoring_account_when_service_reports_down(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="ready-monitoring@example.com",
            name="Ready Monitoring",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        service = Mock()
        service.readiness.return_value = (
            503,
            {"status": "down", "checks": [], "timestamp": "2026-04-20T10:00:00"},
        )
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "down")
        service.readiness.assert_called_once()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_stats_endpoint_returns_401_for_unauthenticated_user(
        self,
        mocked_get_service,
    ):
        response = self.client.get("/monitoring/stats/")

        self.assertEqual(response.status_code, 401)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_stats_endpoint_returns_403_for_inactive_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="inactive-monitoring@example.com",
            name="Inactive Monitoring",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=False)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/stats/")

        self.assertEqual(response.status_code, 403)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_stats_endpoint_returns_200_for_authorized_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="active-monitoring@example.com",
            name="Active Monitoring",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        service = Mock()
        service.stats.return_value = {
            "status": "ok",
            "generated_at": "2026-04-20T10:00:00",
            "totals": {"requests": 2, "errors": 0, "error_rate": 0.0},
            "routes": [],
        }
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/stats/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        service.stats.assert_called_once()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_snapshot_endpoint_returns_access_only_when_monitoring_not_allowed(
        self,
        mocked_get_service,
    ):
        response = self.client.get("/monitoring/snapshot/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "access": {"allowed": False, "reason": "unauthenticated"},
                "ready": None,
                "stats": None,
            },
        )
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_snapshot_endpoint_returns_snapshot_for_authorized_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="snapshot-monitoring@example.com",
            name="Snapshot Monitoring",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        service = Mock()
        service.readiness.return_value = (
            200,
            {
                "status": "ok",
                "timestamp": "2026-04-20T10:00:00",
                "checks": [],
            },
        )
        service.stats.return_value = {
            "status": "ok",
            "generated_at": "2026-04-20T10:00:00",
            "totals": {"requests": 2, "errors": 0, "error_rate": 0.0},
            "routes": [],
            "events": {},
        }
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/snapshot/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["access"],
            {
                "allowed": True,
                "reason": "ok",
            },
        )
        self.assertEqual(response.data["ready"]["status"], "ok")
        self.assertEqual(response.data["stats"]["status"], "ok")
        service.readiness.assert_called_once()
        service.stats.assert_called_once()

    def test_live_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/live/")
        self.assertEqual(response.status_code, 405)

    def test_ready_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/ready/")
        self.assertEqual(response.status_code, 405)

    def test_stats_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/stats/")
        self.assertEqual(response.status_code, 405)

    def test_snapshot_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/snapshot/")
        self.assertEqual(response.status_code, 405)

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_stream_endpoint_returns_401_for_unauthenticated_user(
        self,
        mocked_get_service,
    ):
        response = self.client.get("/monitoring/stream/")

        self.assertEqual(response.status_code, 401)
        mocked_get_service.assert_not_called()

    @patch("monitoring.interfaces.http.views.get_monitoring_service")
    def test_stream_endpoint_returns_sse_payload_for_authorized_monitoring_account(
        self,
        mocked_get_service,
    ):
        user = User.objects.create_user(
            email="stream-monitoring@example.com",
            name="Stream Monitoring",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        service = Mock()
        service.stats.return_value = {
            "status": "ok",
            "generated_at": "2026-04-20T10:00:00",
            "totals": {"requests": 2, "errors": 0, "error_rate": 0.0},
            "routes": [],
            "events": {},
            "timeseries": {"window_seconds": 300, "bucket_seconds": 10, "points": []},
        }
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/stream/?max_events=1")
        first_chunk = next(iter(response.streaming_content))
        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertIn("text/event-stream", response["Content-Type"])
        self.assertIn("event: stats", first_chunk)
        self.assertIn('"status":"ok"', first_chunk)
        service.stats.assert_called_once()

    def test_stream_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/stream/")
        self.assertEqual(response.status_code, 405)

    def test_access_endpoint_returns_unauthenticated_decision(self):
        response = self.client.get("/monitoring/access/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "allowed": False,
                "reason": "unauthenticated",
            },
        )
        self.assertIn("X-RateLimit-Limit", response)
        self.assertIn("X-RateLimit-Remaining", response)

    def test_access_endpoint_returns_no_account_decision_for_verified_user_without_monitoring_account(
        self,
    ):
        user = User.objects.create_user(
            email="access-no-account@example.com",
            name="Access No Account",
            status="verified",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/access/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "allowed": False,
                "reason": "no_account",
            },
        )

    def test_access_endpoint_returns_unverified_decision(self):
        user = User.objects.create_user(
            email="access-unverified@example.com",
            name="Access Unverified",
            status="unverified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/access/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "allowed": False,
                "reason": "unverified",
            },
        )

    def test_access_endpoint_returns_inactive_decision(self):
        user = User.objects.create_user(
            email="access-inactive@example.com",
            name="Access Inactive",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=False)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/access/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "allowed": False,
                "reason": "inactive",
            },
        )

    def test_access_endpoint_returns_ok_decision(self):
        user = User.objects.create_user(
            email="access-ok@example.com",
            name="Access OK",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        self.client.force_authenticate(user=user)

        response = self.client.get("/monitoring/access/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "allowed": True,
                "reason": "ok",
            },
        )

    def test_access_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/access/")
        self.assertEqual(response.status_code, 405)
