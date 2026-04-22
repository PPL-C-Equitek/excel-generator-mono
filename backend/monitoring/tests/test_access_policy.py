from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from authentication.models import User
from monitoring.application.access_policy import MonitoringAccessDecision, MonitoringAccessPolicy
from monitoring.models import MonitoringAccount


class MonitoringAccessDecisionTest(TestCase):
    def test_to_dict_maps_fields(self):
        decision = MonitoringAccessDecision(allowed=True, reason="ok")

        self.assertEqual(
            decision.to_dict(),
            {
                "allowed": True,
                "reason": "ok",
            },
        )


class MonitoringAccessPolicyTest(TestCase):
    def setUp(self):
        self.policy = MonitoringAccessPolicy()

    def test_evaluate_returns_unauthenticated_for_anonymous_user(self):
        decision = self.policy.evaluate(AnonymousUser())

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unauthenticated")

    def test_evaluate_returns_unverified_for_authenticated_non_verified_user(self):
        user = User.objects.create_user(
            email="policy-unverified@example.com",
            name="Policy Unverified",
            status="unverified",
        )

        decision = self.policy.evaluate(user)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unverified")

    def test_evaluate_returns_no_account_for_verified_user_without_monitoring_account(self):
        user = User.objects.create_user(
            email="policy-no-account@example.com",
            name="Policy No Account",
            status="verified",
        )

        decision = self.policy.evaluate(user)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "no_account")

    def test_evaluate_returns_inactive_for_verified_user_with_inactive_monitoring_account(self):
        user = User.objects.create_user(
            email="policy-inactive@example.com",
            name="Policy Inactive",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=False)

        decision = self.policy.evaluate(user)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "inactive")

    def test_evaluate_returns_ok_for_verified_user_with_active_monitoring_account(self):
        user = User.objects.create_user(
            email="policy-ok@example.com",
            name="Policy Ok",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)

        decision = self.policy.evaluate(user)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "ok")

