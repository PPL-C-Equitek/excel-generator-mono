from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch

from authentication.models import User
from monitoring.interfaces.http.permissions import IsMonitoringAccount
from monitoring.models import MonitoringAccount


class IsMonitoringAccountPermissionTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsMonitoringAccount()

    def _request_with_user(self, user):
        request = self.factory.get("/monitoring/stats/")
        request.user = user
        return request

    def test_denies_anonymous_user(self):
        request = self._request_with_user(AnonymousUser())
        self.assertFalse(self.permission.has_permission(request, None))
        self.assertEqual(
            self.permission.message,
            "Authentication credentials were not provided.",
        )

    def test_denies_unverified_user(self):
        user = User.objects.create_user(
            email="permission-unverified@example.com",
            name="Permission Unverified",
            status="unverified",
        )
        request = self._request_with_user(user)

        self.assertFalse(self.permission.has_permission(request, None))
        self.assertEqual(self.permission.message, "Verified account is required.")

    def test_denies_verified_user_without_monitoring_account(self):
        user = User.objects.create_user(
            email="permission-no-account@example.com",
            name="Permission No Account",
            status="verified",
        )
        request = self._request_with_user(user)

        self.assertFalse(self.permission.has_permission(request, None))
        self.assertEqual(
            self.permission.message,
            "Monitoring account access is required.",
        )

    def test_denies_verified_user_with_inactive_monitoring_account(self):
        user = User.objects.create_user(
            email="permission-inactive@example.com",
            name="Permission Inactive",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=False)
        request = self._request_with_user(user)

        self.assertFalse(self.permission.has_permission(request, None))
        self.assertEqual(self.permission.message, "Monitoring account is inactive.")

    def test_allows_verified_user_with_active_monitoring_account(self):
        user = User.objects.create_user(
            email="permission-active@example.com",
            name="Permission Active",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)
        request = self._request_with_user(user)

        self.assertTrue(self.permission.has_permission(request, None))

    def test_unknown_reason_uses_default_message(self):
        class _UnknownReasonDecision:
            allowed = False
            reason = "unexpected_reason"

        class _UnknownReasonPolicy:
            def evaluate(self, user):
                return _UnknownReasonDecision()

        request = self._request_with_user(AnonymousUser())
        with patch(
            "monitoring.interfaces.http.permissions.MonitoringAccessPolicy",
            return_value=_UnknownReasonPolicy(),
        ):
            self.assertFalse(self.permission.has_permission(request, None))

        self.assertEqual(
            self.permission.message,
            "Monitoring account access is required.",
        )
