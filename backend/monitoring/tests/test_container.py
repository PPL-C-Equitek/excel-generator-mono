from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

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

    @override_settings(
        MONITORING_METRICS_BACKEND="redis",
        MONITORING_REDIS_URL="redis://localhost:6379/0",
        MONITORING_REDIS_KEY_PREFIX="monitoring_test",
        MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS=2.0,
        MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS=2.0,
        MONITORING_REALTIME_WINDOW_SECONDS=120,
        MONITORING_REALTIME_BUCKET_SECONDS=15,
        MONITORING_MAX_REALTIME_RECORDS=321,
    )
    @patch("monitoring.container.RedisMetricsRepository")
    def test_build_monitoring_service_uses_redis_repository_when_enabled(self, redis_repository_cls):
        redis_repository = object()
        redis_repository_cls.return_value = redis_repository

        service = container.build_monitoring_service()

        self.assertIs(service._metrics_repository, redis_repository)
        redis_repository_cls.assert_called_once_with(
            redis_url="redis://localhost:6379/0",
            key_prefix="monitoring_test",
            socket_timeout_seconds=2.0,
            connect_timeout_seconds=2.0,
            realtime_window_seconds=120,
            realtime_bucket_seconds=15,
            max_realtime_records=321,
        )

    @override_settings(
        MONITORING_METRICS_BACKEND="redis",
    )
    @patch("monitoring.container.InMemoryMetricsRepository")
    @patch("monitoring.container.RedisMetricsRepository")
    def test_build_monitoring_service_falls_back_to_in_memory_when_redis_fails(
        self,
        redis_repository_cls,
        in_memory_repository_cls,
    ):
        redis_repository_cls.side_effect = RuntimeError("redis unavailable")
        in_memory_repository = object()
        in_memory_repository_cls.return_value = in_memory_repository

        service = container.build_monitoring_service()

        self.assertIs(service._metrics_repository, in_memory_repository)
        redis_repository_cls.assert_called_once()
        in_memory_repository_cls.assert_called_once()
