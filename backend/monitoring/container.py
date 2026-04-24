from monitoring.application.services import MonitoringService, ReadinessService
from monitoring.infrastructure.health_checks import (
    DatabaseHealthCheck,
    OpenAIConfigHealthCheck,
    StorageHealthCheck,
)
from monitoring.infrastructure.repositories import InMemoryMetricsRepository

_monitoring_service: MonitoringService | None = None


def build_monitoring_service() -> MonitoringService:
    checks = [
        DatabaseHealthCheck(),
        StorageHealthCheck(),
        OpenAIConfigHealthCheck(),
    ]
    readiness = ReadinessService(checks=checks)
    repository = InMemoryMetricsRepository()
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
