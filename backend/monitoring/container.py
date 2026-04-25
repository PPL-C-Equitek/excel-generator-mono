import logging

from django.conf import settings

from monitoring.domain.contracts import MonitoringAlertNotifier
from monitoring.application.services import MonitoringService, ReadinessService
from monitoring.infrastructure.health_checks import (
    DatabaseHealthCheck,
    OpenAIConfigHealthCheck,
    RedisHealthCheck,
    StorageHealthCheck,
)
from monitoring.infrastructure.discord_notifier import DiscordWebhookNotifier
from monitoring.infrastructure.repositories import (
    InMemoryMetricsRepository,
    ResilientMetricsRepository,
    RedisMetricsRepository,
    REALTIME_DEFAULT_BUCKET_SECONDS,
    REALTIME_DEFAULT_MAX_RECORDS,
    REALTIME_DEFAULT_WINDOW_SECONDS,
    REDIS_DEFAULT_KEY_NAMESPACE_VERSION,
    REDIS_DEFAULT_KEY_PREFIX,
    REDIS_DEFAULT_KEY_TTL_SECONDS,
    REDIS_DEFAULT_URL,
    ROUTE_DEFAULT_MAX_LATENCY_SAMPLES,
)

MONITORING_DEFAULT_DISCORD_WEBHOOK_TIMEOUT_SECONDS = 3.0
MONITORING_DEFAULT_STATS_CACHE_TTL_SECONDS = 2.0

_monitoring_service: MonitoringService | None = None
logger = logging.getLogger(__name__)


def _monitoring_backend_setting() -> str:
    return str(getattr(settings, "MONITORING_METRICS_BACKEND", "memory")).strip().lower()


def _build_repository_kwargs() -> dict[str, int]:
    max_routes_per_snapshot_setting = getattr(
        settings, "MONITORING_MAX_ROUTES_PER_SNAPSHOT", None
    )
    max_routes_per_snapshot = None
    try:
        parsed_max_routes = int(max_routes_per_snapshot_setting)
        if parsed_max_routes > 0:
            max_routes_per_snapshot = parsed_max_routes
    except (TypeError, ValueError):
        pass

    return {
        "realtime_window_seconds": int(
            getattr(settings, "MONITORING_REALTIME_WINDOW_SECONDS", REALTIME_DEFAULT_WINDOW_SECONDS)
        ),
        "realtime_bucket_seconds": int(
            getattr(settings, "MONITORING_REALTIME_BUCKET_SECONDS", REALTIME_DEFAULT_BUCKET_SECONDS)
        ),
        "max_realtime_records": int(
            getattr(settings, "MONITORING_MAX_REALTIME_RECORDS", REALTIME_DEFAULT_MAX_RECORDS)
        ),
        "max_route_latency_samples": int(
            getattr(
                settings,
                "MONITORING_MAX_ROUTE_LATENCY_SAMPLES",
                ROUTE_DEFAULT_MAX_LATENCY_SAMPLES,
            )
        ),
        "max_routes_per_snapshot": max_routes_per_snapshot,
    }


def _build_redis_repository(*, repository_kwargs: dict[str, int]) -> RedisMetricsRepository:
    redis_url = str(getattr(settings, "MONITORING_REDIS_URL", REDIS_DEFAULT_URL)).strip()
    redis_key_prefix = str(
        getattr(settings, "MONITORING_REDIS_KEY_PREFIX", REDIS_DEFAULT_KEY_PREFIX)
    ).strip()
    redis_key_namespace_version = str(
        getattr(
            settings,
            "MONITORING_REDIS_KEY_NAMESPACE_VERSION",
            REDIS_DEFAULT_KEY_NAMESPACE_VERSION,
        )
    ).strip()
    redis_key_ttl_seconds = int(
        getattr(settings, "MONITORING_REDIS_KEY_TTL_SECONDS", REDIS_DEFAULT_KEY_TTL_SECONDS)
    )
    redis_socket_timeout_seconds = float(
        getattr(settings, "MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS", 1.0)
    )
    redis_connect_timeout_seconds = float(
        getattr(settings, "MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS", 1.0)
    )
    return RedisMetricsRepository(
        redis_url=redis_url,
        key_prefix=redis_key_prefix,
        key_namespace_version=redis_key_namespace_version,
        key_ttl_seconds=redis_key_ttl_seconds,
        socket_timeout_seconds=redis_socket_timeout_seconds,
        connect_timeout_seconds=redis_connect_timeout_seconds,
        **repository_kwargs,
    )


def _build_metrics_repository():
    backend = _monitoring_backend_setting()
    repository_kwargs = _build_repository_kwargs()
    in_memory_repository_kwargs = dict(repository_kwargs)
    in_memory_repository_kwargs.pop("max_routes_per_snapshot", None)
    fallback_repository = InMemoryMetricsRepository(**in_memory_repository_kwargs)

    if backend == "redis":
        try:
            primary_repository = _build_redis_repository(repository_kwargs=repository_kwargs)
            return ResilientMetricsRepository(
                primary_repository=primary_repository,
                fallback_repository=fallback_repository,
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

    return fallback_repository


def _build_readiness_checks():
    checks = [
        DatabaseHealthCheck(),
        StorageHealthCheck(),
        OpenAIConfigHealthCheck(),
    ]
    if _monitoring_backend_setting() == "redis":
        checks.append(
            RedisHealthCheck(
                redis_url=str(getattr(settings, "MONITORING_REDIS_URL", REDIS_DEFAULT_URL)).strip(),
                socket_timeout_seconds=float(
                    getattr(settings, "MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS", 1.0)
                ),
                connect_timeout_seconds=float(
                    getattr(settings, "MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS", 1.0)
                ),
                is_critical=False,
            )
        )
    return checks


def _build_readiness_alert_notifier() -> MonitoringAlertNotifier | None:
    webhook_url = str(getattr(settings, "MONITORING_DISCORD_WEBHOOK_URL", "")).strip()
    if not webhook_url:
        return None

    username = str(getattr(settings, "MONITORING_DISCORD_WEBHOOK_USERNAME", "MonitoringBot")).strip()
    timeout_seconds = float(
        getattr(
            settings,
            "MONITORING_DISCORD_WEBHOOK_TIMEOUT_SECONDS",
            MONITORING_DEFAULT_DISCORD_WEBHOOK_TIMEOUT_SECONDS,
        )
    )
    return DiscordWebhookNotifier(
        webhook_url=webhook_url,
        username=username,
        timeout_seconds=timeout_seconds,
    )


def build_monitoring_service() -> MonitoringService:
    checks = _build_readiness_checks()
    readiness = ReadinessService(checks=checks)
    repository = _build_metrics_repository()
    alert_notifier = _build_readiness_alert_notifier()
    alert_cooldown_seconds = int(
        getattr(
            settings,
            "MONITORING_READINESS_ALERT_COOLDOWN_SECONDS",
            300,
        )
    )
    stats_cache_ttl_seconds = float(
        getattr(
            settings,
            "MONITORING_STATS_CACHE_TTL_SECONDS",
            MONITORING_DEFAULT_STATS_CACHE_TTL_SECONDS,
        )
    )
    return MonitoringService(
        readiness_service=readiness,
        metrics_repository=repository,
        alert_notifier=alert_notifier,
        readiness_alert_cooldown_seconds=alert_cooldown_seconds,
        stats_cache_ttl_seconds=stats_cache_ttl_seconds,
    )


def get_monitoring_service() -> MonitoringService:
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = build_monitoring_service()
    return _monitoring_service


def reset_monitoring_service_for_tests() -> None:
    global _monitoring_service
    _monitoring_service = None
