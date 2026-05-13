import os
from abc import ABC, abstractmethod
from time import perf_counter

from django.conf import settings
from django.db import connections

from monitoring.domain.entities import CheckResult

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


class BaseHealthCheck(ABC):
    name = "base"
    is_critical = True

    def run(self) -> CheckResult:
        started = perf_counter()
        try:
            self.perform_check()
            status = "ok"
            message = ""
        except Exception as exc:
            status = "error"
            message = str(exc) or exc.__class__.__name__

        latency_ms = int((perf_counter() - started) * 1000)
        return CheckResult(
            name=self.name,
            status=status,
            latency_ms=latency_ms,
            is_critical=self.is_critical,
            message=message,
        )

    @abstractmethod
    def perform_check(self) -> None:
        raise NotImplementedError


class DatabaseHealthCheck(BaseHealthCheck):
    name = "database"
    is_critical = True

    def __init__(self, alias: str = "default"):
        self.alias = alias

    def perform_check(self) -> None:
        connection = connections[self.alias]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


class StorageHealthCheck(BaseHealthCheck):
    name = "storage"
    is_critical = True

    def __init__(self, path: str | None = None, *, is_critical: bool = True):
        self.path = path or settings.MEDIA_ROOT
        self.is_critical = is_critical

    def perform_check(self) -> None:
        if not os.path.isdir(self.path):
            raise FileNotFoundError(f"Directory not found: {self.path}")
        if not os.access(self.path, os.W_OK):
            raise PermissionError(f"Directory is not writable: {self.path}")


class OpenAIConfigHealthCheck(BaseHealthCheck):
    name = "openai_config"
    is_critical = False

    def perform_check(self) -> None:
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not isinstance(api_key, str) or not api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is not configured.")


class RedisHealthCheck(BaseHealthCheck):
    name = "redis"
    is_critical = False

    def __init__(
        self,
        *,
        redis_url: str,
        socket_timeout_seconds: float = 1.0,
        connect_timeout_seconds: float = 1.0,
        is_critical: bool = False,
        redis_client=None,
    ):
        self._redis_url = redis_url
        self._socket_timeout_seconds = float(socket_timeout_seconds)
        self._connect_timeout_seconds = float(connect_timeout_seconds)
        self.is_critical = bool(is_critical)
        self._redis_client = redis_client

    def perform_check(self) -> None:
        if self._redis_client is None:
            if redis is None:
                raise RuntimeError("Redis dependency is missing.")
            self._redis_client = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_timeout=self._socket_timeout_seconds,
                socket_connect_timeout=self._connect_timeout_seconds,
            )
        self._redis_client.ping()
