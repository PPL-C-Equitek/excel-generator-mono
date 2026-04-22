from unittest.mock import patch

from django.test import SimpleTestCase

from monitoring import container
from monitoring.services import MonitoringService


class MonitoringContainerTest(SimpleTestCase):
    def tearDown(self):
        container.reset_monitoring_service_for_tests()

    def test_build_monitoring_service_returns_fully_wired_service(self):
        service = container.build_monitoring_service()

        self.assertIsInstance(service, MonitoringService)
        checks = service._readiness_service._checks
        self.assertEqual(len(checks), 3)
        self.assertEqual([check.name for check in checks], ["database", "storage", "openai_config"])

    def test_get_monitoring_service_builds_once_and_reuses_instance(self):
        sentinel = object()
        with patch("monitoring.container.build_monitoring_service", return_value=sentinel) as builder:
            first = container.get_monitoring_service()
            second = container.get_monitoring_service()

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        builder.assert_called_once()

    def test_reset_monitoring_service_for_tests_clears_cached_instance(self):
        first = container.get_monitoring_service()
        container.reset_monitoring_service_for_tests()
        second = container.get_monitoring_service()

        self.assertIsNot(first, second)

