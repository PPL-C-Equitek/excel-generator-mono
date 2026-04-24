import logging

from django.conf import settings

from monitoring.application.services import MonitoringService, ReadinessService
from monitoring.infrastructure.health_checks import (
    DatabaseHealthCheck,
    OpenAIConfigHealthCheck,
    StorageHealthCheck,
)
from monitoring.infrastructure.repositories import (
    InMemoryMetricsRepository,
    RedisMetricsRepository,
    REALTIME_DEFAULT_BUCKET_SECONDS,
    REALTIME_DEFAULT_MAX_RECORDS,
    REALTIME_DEFAULT_WINDOW_SECONDS,
)

_monitoring_service: MonitoringService | None = None
logger = logging.getLogger(__name__)


def _build_metrics_repository():
    backend = str(getattr(settings, "MONITORING_METRICS_BACKEND", "memory")).strip().lower()
    realtime_window_seconds = int(
        getattr(settings, "MONITORING_REALTIME_WINDOW_SECONDS", REALTIME_DEFAULT_WINDOW_SECONDS)
    )
    realtime_bucket_seconds = int(
        getattr(settings, "MONITORING_REALTIME_BUCKET_SECONDS", REALTIME_DEFAULT_BUCKET_SECONDS)
    )
    max_realtime_records = int(
        getattr(settings, "MONITORING_MAX_REALTIME_RECORDS", REALTIME_DEFAULT_MAX_RECORDS)
    )

    repository_kwargs = {
        "realtime_window_seconds": realtime_window_seconds,
        "realtime_bucket_seconds": realtime_bucket_seconds,
        "max_realtime_records": max_realtime_records,
    }

    if backend == "redis":
        redis_url = str(
            getattr(settings, "MONITORING_REDIS_URL", "redis://127.0.0.1:6379/0")
        ).strip()
        redis_key_prefix = str(
            getattr(settings, "MONITORING_REDIS_KEY_PREFIX", "monitoring")
        ).strip()
        redis_socket_timeout_seconds = float(
            getattr(settings, "MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS", 1.0)
        )
        redis_connect_timeout_seconds = float(
            getattr(settings, "MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS", 1.0)
        )

        try:
            return RedisMetricsRepository(
                redis_url=redis_url,
                key_prefix=redis_key_prefix,
                socket_timeout_seconds=redis_socket_timeout_seconds,
                connect_timeout_seconds=redis_connect_timeout_seconds,
                **repository_kwargs,
            )
        except Exception:
            logger.exception(
                "Failed to initialize Redis monitoring repository. Falling back to in-memory repository."
            )

    elif backend != "memory":
        logger.warning(
            "Unsupported MONITORING_METRICS_BACKEND '%s'. Falling back to in-memory repository.",
            backend,
        )

    return InMemoryMetricsRepository(**repository_kwargs)


def build_monitoring_service() -> MonitoringService:
    checks = [
        DatabaseHealthCheck(),
        StorageHealthCheck(),
        OpenAIConfigHealthCheck(),
    ]
    readiness = ReadinessService(checks=checks)
    repository = _build_metrics_repository()
    return MonitoringService(
        readiness_service=readiness,
        metrics_repository=repository,
    )


def get_monitoring_service() -> MonitoringService:
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = build_monitoring_service()
    return _monitoring_service


def reset_monitoring_service_for_tests() -> None:
    global _monitoring_service
    _monitoring_service = None
