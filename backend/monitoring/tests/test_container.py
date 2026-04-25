from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from monitoring import container
from monitoring.services import MonitoringService


class MonitoringContainerTest(SimpleTestCase):
    def test_monitoring_backend_setting_normalizes_value(self):
        with patch("monitoring.container.settings") as settings:
            settings.MONITORING_METRICS_BACKEND = "Redis "
            self.assertEqual(container._monitoring_backend_setting(), "redis")

    @override_settings(
        MONITORING_REALTIME_WINDOW_SECONDS="75",
        MONITORING_REALTIME_BUCKET_SECONDS="8",
        MONITORING_MAX_REALTIME_RECORDS="200",
        MONITORING_MAX_ROUTE_LATENCY_SAMPLES="512",
    )
    def test_build_repository_kwargs_reads_settings(self):
        self.assertEqual(
            container._build_repository_kwargs(),
            {
                "realtime_window_seconds": 75,
                "realtime_bucket_seconds": 8,
                "max_realtime_records": 200,
                "max_route_latency_samples": 512,
            },
        )

    @override_settings(MONITORING_METRICS_BACKEND="memory")
    def test_build_readiness_checks_does_not_include_redis_check_by_default(self):
        checks = container._build_readiness_checks()

        self.assertEqual([check.name for check in checks], ["database", "storage", "openai_config"])

    @override_settings(MONITORING_METRICS_BACKEND="unknown")
    @patch("monitoring.container.InMemoryMetricsRepository")
    @patch("monitoring.container.RedisMetricsRepository")
    def test_build_metrics_repository_falls_back_to_in_memory_for_unsupported_backend(
        self,
        redis_repository_cls,
        in_memory_repository_cls,
    ):
        fallback_repository = object()
        in_memory_repository_cls.return_value = fallback_repository

        result = container._build_metrics_repository()

        self.assertIs(result, fallback_repository)
        redis_repository_cls.assert_not_called()
        in_memory_repository_cls.assert_called_once()

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
        MONITORING_REDIS_KEY_NAMESPACE_VERSION="v2",
        MONITORING_REDIS_KEY_TTL_SECONDS=7200,
        MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS=2.0,
        MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS=2.0,
        MONITORING_REALTIME_WINDOW_SECONDS=120,
        MONITORING_REALTIME_BUCKET_SECONDS=15,
        MONITORING_MAX_REALTIME_RECORDS=321,
        MONITORING_MAX_ROUTE_LATENCY_SAMPLES=123,
    )
    @patch("monitoring.container.ResilientMetricsRepository")
    @patch("monitoring.container.InMemoryMetricsRepository")
    @patch("monitoring.container.RedisMetricsRepository")
    def test_build_monitoring_service_uses_redis_repository_when_enabled(
        self,
        redis_repository_cls,
        in_memory_repository_cls,
        resilient_repository_cls,
    ):
        redis_repository = object()
        fallback_repository = object()
        resilient_repository = object()
        redis_repository_cls.return_value = redis_repository
        in_memory_repository_cls.return_value = fallback_repository
        resilient_repository_cls.return_value = resilient_repository

        service = container.build_monitoring_service()

        self.assertIs(service._metrics_repository, resilient_repository)
        redis_repository_cls.assert_called_once_with(
            redis_url="redis://localhost:6379/0",
            key_prefix="monitoring_test",
            key_namespace_version="v2",
            key_ttl_seconds=7200,
            socket_timeout_seconds=2.0,
            connect_timeout_seconds=2.0,
            realtime_window_seconds=120,
            realtime_bucket_seconds=15,
            max_realtime_records=321,
            max_route_latency_samples=123,
        )
        in_memory_repository_cls.assert_called_once_with(
            realtime_window_seconds=120,
            realtime_bucket_seconds=15,
            max_realtime_records=321,
            max_route_latency_samples=123,
        )
        resilient_repository_cls.assert_called_once_with(
            primary_repository=redis_repository,
            fallback_repository=fallback_repository,
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

    @override_settings(MONITORING_METRICS_BACKEND="redis")
    def test_build_monitoring_service_adds_redis_check_when_backend_is_redis(self):
        service = container.build_monitoring_service()

        checks = service._readiness_service._checks
        self.assertEqual([check.name for check in checks], ["database", "storage", "openai_config", "redis"])
