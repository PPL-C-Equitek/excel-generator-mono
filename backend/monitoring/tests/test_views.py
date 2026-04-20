from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from authentication.models import User
from monitoring.models import MonitoringAccount


@override_settings(ROOT_URLCONF="monitoring.urls")
class MonitoringViewsTest(APITestCase):
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

    def test_live_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/live/")
        self.assertEqual(response.status_code, 405)

    def test_ready_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/ready/")
        self.assertEqual(response.status_code, 405)

    def test_stats_endpoint_rejects_post_method(self):
        response = self.client.post("/monitoring/stats/")
        self.assertEqual(response.status_code, 405)

