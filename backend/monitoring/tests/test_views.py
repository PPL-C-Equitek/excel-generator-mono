from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APISimpleTestCase


@override_settings(ROOT_URLCONF="monitoring.urls")
class MonitoringViewsTest(APISimpleTestCase):
    @patch("monitoring.views.get_monitoring_service")
    def test_live_endpoint_returns_payload(self, mocked_get_service):
        service = Mock()
        service.live.return_value = {"status": "ok", "timestamp": "2026-04-20T10:00:00"}
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"status": "ok", "timestamp": "2026-04-20T10:00:00"},
        )
        service.live.assert_called_once()

    @patch("monitoring.views.get_monitoring_service")
    def test_ready_endpoint_uses_service_http_status(self, mocked_get_service):
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

    @patch("monitoring.views.get_monitoring_service")
    @override_settings(MONITORING_API_TOKEN="")
    def test_stats_endpoint_allows_access_when_token_not_configured(
        self,
        mocked_get_service,
    ):
        service = Mock()
        service.stats.return_value = {
            "status": "ok",
            "generated_at": "2026-04-20T10:00:00",
            "totals": {"requests": 0, "errors": 0, "error_rate": 0.0},
            "routes": [],
        }
        mocked_get_service.return_value = service

        response = self.client.get("/monitoring/stats/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        service.stats.assert_called_once()

    @patch("monitoring.views.get_monitoring_service")
    @override_settings(MONITORING_API_TOKEN="secret-token")
    def test_stats_endpoint_rejects_missing_token_header(self, mocked_get_service):
        response = self.client.get("/monitoring/stats/")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Unauthorized monitoring access.")
        mocked_get_service.assert_not_called()

    @patch("monitoring.views.get_monitoring_service")
    @override_settings(MONITORING_API_TOKEN="secret-token")
    def test_stats_endpoint_rejects_invalid_token_header(self, mocked_get_service):
        response = self.client.get(
            "/monitoring/stats/",
            HTTP_X_MONITORING_TOKEN="wrong-token",
        )

        self.assertEqual(response.status_code, 403)
        mocked_get_service.assert_not_called()

    @patch("monitoring.views.get_monitoring_service")
    @override_settings(MONITORING_API_TOKEN="secret-token")
    def test_stats_endpoint_accepts_valid_token_header(self, mocked_get_service):
        service = SimpleNamespace(
            stats=lambda: {
                "status": "ok",
                "generated_at": "2026-04-20T10:00:00",
                "totals": {"requests": 2, "errors": 0, "error_rate": 0.0},
                "routes": [],
            }
        )
        mocked_get_service.return_value = service

        response = self.client.get(
            "/monitoring/stats/",
            HTTP_X_MONITORING_TOKEN="  secret-token  ",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        mocked_get_service.assert_called_once()

