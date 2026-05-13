from unittest.mock import patch

from django.test import TestCase

from authentication.models import User
from authentication.register.adapters import DjangoRegistrationWriterRepository
from monitoring.models import MonitoringAccount


class MonitoringAccountManagerTest(TestCase):
    def test_provision_for_user_raises_value_error_when_user_missing(self):
        with self.assertRaises(ValueError):
            MonitoringAccount.objects.provision_for_user(user=None)

    def test_provision_for_user_creates_new_active_account(self):
        user = User.objects.create_user(
            email="monitoring-create@example.com",
            name="Monitoring Create",
            status="verified",
        )

        account, created = MonitoringAccount.objects.provision_for_user(user=user)

        self.assertTrue(created)
        self.assertTrue(account.is_active)
        self.assertEqual(account.user, user)

    def test_provision_for_user_returns_existing_without_updating_when_same_flag(self):
        user = User.objects.create_user(
            email="monitoring-existing@example.com",
            name="Monitoring Existing",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=True)

        with patch("monitoring.models.MonitoringAccount.save") as mocked_save:
            account, created = MonitoringAccount.objects.provision_for_user(
                user=user,
                is_active=True,
            )

        self.assertFalse(created)
        self.assertTrue(account.is_active)
        mocked_save.assert_not_called()

    def test_provision_for_user_updates_active_flag_when_changed(self):
        user = User.objects.create_user(
            email="monitoring-update@example.com",
            name="Monitoring Update",
            status="verified",
        )
        MonitoringAccount.objects.create(user=user, is_active=False)

        account, created = MonitoringAccount.objects.provision_for_user(
            user=user,
            is_active=True,
        )

        self.assertFalse(created)
        self.assertTrue(account.is_active)
        refreshed = MonitoringAccount.objects.get(user=user)
        self.assertTrue(refreshed.is_active)


class MonitoringAccountModelTest(TestCase):
    def test_str_returns_email_and_status_active(self):
        user = User.objects.create_user(
            email="monitoring-str@example.com",
            name="Monitoring Str",
            status="verified",
        )
        account = MonitoringAccount.objects.create(user=user, is_active=True)

        self.assertEqual(str(account), "monitoring-str@example.com (active)")

    def test_str_returns_email_and_status_inactive(self):
        user = User.objects.create_user(
            email="monitoring-str-inactive@example.com",
            name="Monitoring Str Inactive",
            status="verified",
        )
        account = MonitoringAccount.objects.create(user=user, is_active=False)

        self.assertEqual(str(account), "monitoring-str-inactive@example.com (inactive)")

    def test_has_access_true_for_active_verified_account(self):
        user = User.objects.create_user(
            email="monitoring-access-true@example.com",
            name="Monitoring Access True",
            status="verified",
        )
        account = MonitoringAccount.objects.create(user=user, is_active=True)

        self.assertTrue(account.has_access)

    def test_has_access_false_for_inactive_account(self):
        user = User.objects.create_user(
            email="monitoring-access-inactive@example.com",
            name="Monitoring Access Inactive",
            status="verified",
        )
        account = MonitoringAccount.objects.create(user=user, is_active=False)

        self.assertFalse(account.has_access)

    def test_has_access_false_for_unverified_user(self):
        user = User.objects.create_user(
            email="monitoring-access-unverified@example.com",
            name="Monitoring Access Unverified",
            status="unverified",
        )
        account = MonitoringAccount.objects.create(user=user, is_active=True)

        self.assertFalse(account.has_access)


class MonitoringAccountProvisioningFlowTest(TestCase):
    def test_register_writer_does_not_create_monitoring_account(self):
        repository = DjangoRegistrationWriterRepository()

        repository.create_unverified_user(
            name="Normal Registered User",
            email="normal-user@example.com",
        )

        user = User.objects.get(email="normal-user@example.com")
        self.assertEqual(user.status, "unverified")
        self.assertFalse(
            MonitoringAccount.objects.filter(user=user).exists(),
        )

