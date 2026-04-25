import math
import logging
from collections.abc import Iterable
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from threading import Lock
from typing import Callable
from uuid import uuid4

from monitoring.domain.entities import (
    AuthMetricEvent,
    EventMetricSnapshot,
    MetricsSnapshot,
    RealtimeMetricPoint,
    RequestMetricEvent,
    RouteMetricSnapshot,
)

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

UNKNOWN_ROUTE = "unknown"
UNKNOWN_METHOD = "UNKNOWN"
UNKNOWN_VALUE = "unknown"
REALTIME_DEFAULT_WINDOW_SECONDS = 5 * 60
REALTIME_DEFAULT_BUCKET_SECONDS = 10
REALTIME_DEFAULT_MAX_RECORDS = 10_000
ROUTE_DEFAULT_MAX_LATENCY_SAMPLES = 2_048
REDIS_DEFAULT_URL = "redis://127.0.0.1:6379/0"
REDIS_DEFAULT_KEY_PREFIX = "monitoring"
REDIS_DEFAULT_KEY_NAMESPACE_VERSION = "v1"
REDIS_DEFAULT_KEY_TTL_SECONDS = 86_400
REDIS_FIELD_ROUTE = "route"
REDIS_FIELD_METHOD = "method"
REDIS_FIELD_TOTAL_REQUESTS = "total_requests"
REDIS_FIELD_TOTAL_ERRORS = "total_errors"
REDIS_FIELD_TOTAL_LATENCY_MS = "total_latency_ms"
REDIS_FIELD_MAX_LATENCY_MS = "max_latency_ms"
REDIS_KEY_SEPARATOR = "\x1f"
logger = logging.getLogger(__name__)
_REDIS_ROUTE_SNAPSHOT_FIELDS = (
    REDIS_FIELD_ROUTE,
    REDIS_FIELD_METHOD,
    REDIS_FIELD_TOTAL_REQUESTS,
    REDIS_FIELD_TOTAL_ERRORS,
    REDIS_FIELD_TOTAL_LATENCY_MS,
    REDIS_FIELD_MAX_LATENCY_MS,
)


@dataclass
class _RouteAccumulator:
    total_requests: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    max_latency_samples: int = ROUTE_DEFAULT_MAX_LATENCY_SAMPLES
    latency_samples: deque[float] = field(default_factory=deque)
    precomputed_p95_latency_ms: float | None = None
    precomputed_p99_latency_ms: float | None = None

    def register(self, event: RequestMetricEvent) -> None:
        duration_ms = max(0.0, float(event.duration_ms))
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        self.max_latency_ms = max(self.max_latency_ms, duration_ms)
        self.latency_samples.append(duration_ms)
        while len(self.latency_samples) > self.max_latency_samples:
            self.latency_samples.popleft()
        self.precomputed_p95_latency_ms = None
        self.precomputed_p99_latency_ms = None
        if event.status_code >= 500:
            self.total_errors += 1

    def to_snapshot(self, route: str, method: str) -> RouteMetricSnapshot:
        p95_latency_ms, p99_latency_ms = self._resolve_percentiles()
        return RouteMetricSnapshot(
            route=route,
            method=method,
            total_requests=self.total_requests,
            total_errors=self.total_errors,
            avg_latency_ms=self._average_latency_ms(),
            max_latency_ms=self.max_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms,
        )

    def _average_latency_ms(self) -> float:
        if self.total_requests <= 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    def _resolve_percentiles(self) -> tuple[float, float]:
        if (
            self.precomputed_p95_latency_ms is not None
            and self.precomputed_p99_latency_ms is not None
        ):
            return (
                max(0.0, float(self.precomputed_p95_latency_ms)),
                max(0.0, float(self.precomputed_p99_latency_ms)),
            )
        if not self.latency_samples:
            return 0.0, 0.0

        sorted_samples = sorted(self.latency_samples)
        return (
            self._percentile(sorted_samples=sorted_samples, percentile=0.95),
            self._percentile(sorted_samples=sorted_samples, percentile=0.99),
        )

    @staticmethod
    def _percentile(*, sorted_samples: list[float], percentile: float) -> float:
        if not sorted_samples:
            return 0.0
        percentile = max(0.0, min(1.0, float(percentile)))
        rank = int(math.ceil(percentile * len(sorted_samples))) - 1
        rank = max(0, min(rank, len(sorted_samples) - 1))
        return max(0.0, float(sorted_samples[rank]))


@dataclass(frozen=True)
class RedisConnectionSettings:
    redis_url: str = REDIS_DEFAULT_URL
    socket_timeout_seconds: float = 1.0
    connect_timeout_seconds: float = 1.0


@dataclass(frozen=True)
class RedisNamespaceSettings:
    key_prefix: str = REDIS_DEFAULT_KEY_PREFIX
    key_namespace_version: str = REDIS_DEFAULT_KEY_NAMESPACE_VERSION


@dataclass(frozen=True)
class _RealtimeRequestRecord:
    created_at: datetime
    is_error: bool
    duration_ms: float


@dataclass
class _RealtimeBucketAccumulator:
    requests: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0

    def register(self, record: _RealtimeRequestRecord) -> None:
        self.requests += 1
        self.total_latency_ms += record.duration_ms
        if record.is_error:
            self.errors += 1

    def to_snapshot(self, bucket_timestamp: datetime) -> RealtimeMetricPoint:
        avg_latency_ms = (
            self.total_latency_ms / self.requests
            if self.requests > 0
            else 0.0
        )
        return RealtimeMetricPoint(
            timestamp=bucket_timestamp,
            requests=self.requests,
            errors=self.errors,
            avg_latency_ms=avg_latency_ms,
        )


@dataclass(frozen=True)
class _RealtimeSeriesConfig:
    window_seconds: int
    bucket_seconds: int
    max_records: int


def _build_realtime_series_config(
    *,
    realtime_window_seconds: int,
    realtime_bucket_seconds: int,
    max_realtime_records: int,
) -> _RealtimeSeriesConfig:
    window_seconds = max(1, int(realtime_window_seconds))
    bucket_seconds = max(1, int(realtime_bucket_seconds))
    if bucket_seconds > window_seconds:
        bucket_seconds = window_seconds
    max_records = max(1, int(max_realtime_records))
    return _RealtimeSeriesConfig(
        window_seconds=window_seconds,
        bucket_seconds=bucket_seconds,
        max_records=max_records,
    )


def _normalize_max_latency_samples(value: int) -> int:
    return max(1, int(value))


class _MetricKeyNormalizerMixin:
    @staticmethod
    def _normalize_text(
        value: str | bytes | None,
        *,
        default: str,
        transform: Callable[[str], str] | None = None,
    ) -> str:
        if value is None:
            normalized = ""
        elif isinstance(value, bytes):
            normalized = value.decode("utf-8", errors="ignore").strip()
        elif isinstance(value, str):
            normalized = value.strip()
        else:
            normalized = str(value).strip()
        if not normalized:
            return default
        if transform is None:
            return normalized
        return transform(normalized)

    @classmethod
    def _normalize_pair(
        cls,
        *,
        first: str | None,
        second: str | None,
        first_default: str,
        second_default: str,
        first_transform: Callable[[str], str] | None = None,
        second_transform: Callable[[str], str] | None = None,
    ) -> tuple[str, str]:
        return (
            cls._normalize_text(first, default=first_default, transform=first_transform),
            cls._normalize_text(second, default=second_default, transform=second_transform),
        )

    @classmethod
    def _route_key_from_event(cls, event: RequestMetricEvent) -> tuple[str, str]:
        return cls._normalize_pair(
            first=event.route,
            second=event.method,
            first_default=UNKNOWN_ROUTE,
            second_default=UNKNOWN_METHOD,
            second_transform=str.upper,
        )

    @classmethod
    def _event_key_from_event(cls, event: AuthMetricEvent) -> tuple[str, str]:
        return cls._normalize_pair(
            first=event.event_name,
            second=event.outcome,
            first_default=UNKNOWN_VALUE,
            second_default=UNKNOWN_VALUE,
            first_transform=str.lower,
            second_transform=str.lower,
        )


class _SnapshotFactory:
    @staticmethod
    def _build_sorted_snapshots(
        *,
        items: list[tuple[tuple[str, str], object]],
        build_snapshot,
        sort_key,
    ) -> list:
        snapshots = [
            build_snapshot(
                item_key=item_key,
                item_payload=item_payload,
            )
            for item_key, item_payload in items
        ]
        snapshots.sort(key=sort_key)
        return snapshots

    @staticmethod
    def build_route_snapshots(
        items: list[tuple[tuple[str, str], _RouteAccumulator]]
    ) -> list[RouteMetricSnapshot]:
        return _SnapshotFactory._build_sorted_snapshots(
            items=items,
            build_snapshot=lambda *, item_key, item_payload: item_payload.to_snapshot(
                route=item_key[0],
                method=item_key[1],
            ),
            sort_key=lambda item: (-item.total_requests, item.route, item.method),
        )

    @staticmethod
    def build_event_snapshots(
        event_items: list[tuple[tuple[str, str], int]]
    ) -> list[EventMetricSnapshot]:
        return _SnapshotFactory._build_sorted_snapshots(
            items=event_items,
            build_snapshot=lambda *, item_key, item_payload: EventMetricSnapshot(
                event_name=item_key[0],
                outcome=item_key[1],
                count=item_payload,
            ),
            sort_key=lambda item: (-item.count, item.event_name, item.outcome),
        )


class _RealtimeSeriesBuilder:
    def __init__(self, *, window_seconds: int, bucket_seconds: int):
        self._window_seconds = window_seconds
        self._bucket_seconds = bucket_seconds

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    @property
    def bucket_seconds(self) -> int:
        return self._bucket_seconds

    def build_points(
        self,
        *,
        records: Iterable[_RealtimeRequestRecord],
        now_epoch: float,
    ) -> list[RealtimeMetricPoint]:
        bucket_count = max(
            1,
            int(math.ceil(self._window_seconds / self._bucket_seconds)),
        )
        effective_window_seconds = bucket_count * self._bucket_seconds
        window_start_epoch = now_epoch - effective_window_seconds
        buckets = [_RealtimeBucketAccumulator() for _ in range(bucket_count)]

        for record in records:
            record_epoch = self.to_epoch_seconds(record.created_at)
            if record_epoch < window_start_epoch:
                continue

            index = int((record_epoch - window_start_epoch) // self._bucket_seconds)
            if index >= bucket_count:
                index = bucket_count - 1
            buckets[index].register(record)

        points: list[RealtimeMetricPoint] = []
        for index, bucket in enumerate(buckets):
            bucket_end_epoch = window_start_epoch + (index + 1) * self._bucket_seconds
            points.append(
                bucket.to_snapshot(
                    bucket_timestamp=self.utc_datetime_from_epoch(bucket_end_epoch)
                )
            )
        return points

    @staticmethod
    def to_epoch_seconds(value: datetime) -> float:
        if value.tzinfo is None:
            return float(value.replace(tzinfo=timezone.utc).timestamp())
        return float(value.astimezone(timezone.utc).timestamp())

    @staticmethod
    def utc_datetime_from_epoch(epoch_seconds: float) -> datetime:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).replace(
            tzinfo=None
        )


def _build_realtime_repository_state(
    *,
    realtime_window_seconds: int,
    realtime_bucket_seconds: int,
    max_realtime_records: int,
    max_route_latency_samples: int,
) -> tuple[
    int,
    int,
    int,
    int,
    _RealtimeSeriesBuilder,
]:
    realtime_config = _build_realtime_series_config(
        realtime_window_seconds=realtime_window_seconds,
        realtime_bucket_seconds=realtime_bucket_seconds,
        max_realtime_records=max_realtime_records,
    )
    realtime_window_seconds = realtime_config.window_seconds
    realtime_bucket_seconds = realtime_config.bucket_seconds
    max_realtime_records = realtime_config.max_records
    max_route_latency_samples = _normalize_max_latency_samples(
        max_route_latency_samples
    )
    realtime_series_builder = _RealtimeSeriesBuilder(
        window_seconds=realtime_window_seconds,
        bucket_seconds=realtime_bucket_seconds,
    )
    return (
        realtime_window_seconds,
        realtime_bucket_seconds,
        max_realtime_records,
        max_route_latency_samples,
        realtime_series_builder,
    )


class _RepositoryRealtimeMixin:
    def _apply_realtime_state(
        self,
        *,
        realtime_window_seconds: int,
        realtime_bucket_seconds: int,
        max_realtime_records: int,
        max_route_latency_samples: int,
    ) -> None:
        (
            self._realtime_window_seconds,
            self._realtime_bucket_seconds,
            self._max_realtime_records,
            self._max_route_latency_samples,
            self._realtime_series_builder,
        ) = _build_realtime_repository_state(
            realtime_window_seconds=realtime_window_seconds,
            realtime_bucket_seconds=realtime_bucket_seconds,
            max_realtime_records=max_realtime_records,
            max_route_latency_samples=max_route_latency_samples,
        )

    def _build_snapshot_response(
        self,
        *,
        now_value: datetime,
        route_items: list[tuple[tuple[str, str], _RouteAccumulator]],
        event_items: list[tuple[tuple[str, str], int]],
        realtime_records: list[_RealtimeRequestRecord],
    ) -> MetricsSnapshot:
        return _build_snapshot_response(
            now_value=now_value,
            route_items=route_items,
            event_items=event_items,
            realtime_records=realtime_records,
            realtime_series_builder=self._realtime_series_builder,
            realtime_window_seconds=self._realtime_window_seconds,
            realtime_bucket_seconds=self._realtime_bucket_seconds,
        )


def _build_snapshot_response(
    *,
    now_value: datetime,
    route_items: list[tuple[tuple[str, str], _RouteAccumulator]],
    event_items: list[tuple[tuple[str, str], int]],
    realtime_records: list[_RealtimeRequestRecord],
    realtime_series_builder: _RealtimeSeriesBuilder,
    realtime_window_seconds: int,
    realtime_bucket_seconds: int,
) -> MetricsSnapshot:
    route_snapshots = _SnapshotFactory.build_route_snapshots(route_items)
    event_snapshots = _SnapshotFactory.build_event_snapshots(event_items)
    realtime_points = realtime_series_builder.build_points(
        records=realtime_records,
        now_epoch=realtime_series_builder.to_epoch_seconds(now_value),
    )
    total_requests = sum(item.total_requests for item in route_snapshots)
    total_errors = sum(item.total_errors for item in route_snapshots)
    return MetricsSnapshot(
        generated_at=now_value,
        total_requests=total_requests,
        total_errors=total_errors,
        routes=tuple(route_snapshots),
        events=tuple(event_snapshots),
        timeseries=tuple(realtime_points),
        timeseries_window_seconds=realtime_window_seconds,
        timeseries_bucket_seconds=realtime_bucket_seconds,
    )


class InMemoryMetricsRepository(_MetricKeyNormalizerMixin, _RepositoryRealtimeMixin):
    def __init__(
        self,
        *,
        now: Callable[[], datetime] | None = None,
        realtime_window_seconds: int = REALTIME_DEFAULT_WINDOW_SECONDS,
        realtime_bucket_seconds: int = REALTIME_DEFAULT_BUCKET_SECONDS,
        max_realtime_records: int = REALTIME_DEFAULT_MAX_RECORDS,
        max_route_latency_samples: int = ROUTE_DEFAULT_MAX_LATENCY_SAMPLES,
    ):
        self._now = now or datetime.utcnow
        self._lock = Lock()
        self._routes: dict[tuple[str, str], _RouteAccumulator] = {}
        self._events: dict[tuple[str, str], int] = {}
        self._apply_realtime_state(
            realtime_window_seconds=realtime_window_seconds,
            realtime_bucket_seconds=realtime_bucket_seconds,
            max_realtime_records=max_realtime_records,
            max_route_latency_samples=max_route_latency_samples,
        )
        self._recent_requests: deque[_RealtimeRequestRecord] = deque()

    def record_request(self, event: RequestMetricEvent) -> None:
        key = self._route_key_from_event(event)
        now_epoch = self._realtime_series_builder.to_epoch_seconds(self._now())
        with self._lock:
            accumulator = self._routes.get(key)
            if accumulator is None:
                accumulator = _RouteAccumulator(
                    max_latency_samples=self._max_route_latency_samples
                )
                self._routes[key] = accumulator
            accumulator.register(event)
            self._append_realtime_record(event)
            self._prune_realtime_records(now_epoch=now_epoch)

    def record_event(self, event: AuthMetricEvent) -> None:
        key = self._event_key_from_event(event)
        with self._lock:
            self._events[key] = self._events.get(key, 0) + 1

    def get_snapshot(self) -> MetricsSnapshot:
        now_value = self._now()
        now_epoch = self._realtime_series_builder.to_epoch_seconds(now_value)
        with self._lock:
            items = list(self._routes.items())
            event_items = list(self._events.items())
            self._prune_realtime_records(now_epoch=now_epoch)
            realtime_records = list(self._recent_requests)

        return self._build_snapshot_response(
            now_value=now_value,
            route_items=items,
            event_items=event_items,
            realtime_records=realtime_records,
        )

    def reset(self) -> None:
        with self._lock:
            self._routes.clear()
            self._events.clear()
            self._recent_requests.clear()

    def _append_realtime_record(self, event: RequestMetricEvent) -> None:
        self._recent_requests.append(
            _RealtimeRequestRecord(
                created_at=event.created_at,
                is_error=event.status_code >= 500,
                duration_ms=max(0.0, float(event.duration_ms)),
            )
        )
        while len(self._recent_requests) > self._max_realtime_records:
            self._recent_requests.popleft()

    def _prune_realtime_records(self, *, now_epoch: float) -> None:
        min_epoch = now_epoch - self._realtime_window_seconds
        while self._recent_requests:
            oldest = self._recent_requests[0]
            if self._realtime_series_builder.to_epoch_seconds(oldest.created_at) >= min_epoch:
                break
            self._recent_requests.popleft()


class ResilientMetricsRepository:
    def __init__(
        self,
        *,
        primary_repository,
        fallback_repository,
    ):
        self._primary_repository = primary_repository
        self._fallback_repository = fallback_repository
        self._degraded_to_fallback = False
        self._lock = Lock()

    @property
    def degraded_to_fallback(self) -> bool:
        with self._lock:
            return self._degraded_to_fallback

    def record_request(self, event: RequestMetricEvent) -> None:
        self._run_with_fallback("record_request", event)

    def record_event(self, event: AuthMetricEvent) -> None:
        self._run_with_fallback("record_event", event)

    def get_snapshot(self) -> MetricsSnapshot:
        return self._run_with_fallback("get_snapshot")

    def reset(self) -> None:
        try:
            self._fallback_repository.reset()
        except Exception:
            logger.exception("Failed to reset fallback monitoring repository.")

        try:
            self._primary_repository.reset()
        except Exception:
            logger.exception("Failed to reset primary monitoring repository.")

    def _run_with_fallback(self, method_name: str, *args):
        if self.degraded_to_fallback:
            method = getattr(self._fallback_repository, method_name)
            return method(*args)

        method = getattr(self._primary_repository, method_name)
        try:
            return method(*args)
        except Exception:
            self._mark_degraded()
            logger.exception(
                "Primary monitoring repository failed during %s. Using fallback repository.",
                method_name,
            )
            fallback_method = getattr(self._fallback_repository, method_name)
            return fallback_method(*args)

    def _mark_degraded(self) -> None:
        with self._lock:
            self._degraded_to_fallback = True


class RedisMetricsRepository(_MetricKeyNormalizerMixin, _RepositoryRealtimeMixin):
    def __init__(
        self,
        *,
        key_namespace_settings: RedisNamespaceSettings | None = None,
        now: Callable[[], datetime] | None = None,
        realtime_window_seconds: int = REALTIME_DEFAULT_WINDOW_SECONDS,
        realtime_bucket_seconds: int = REALTIME_DEFAULT_BUCKET_SECONDS,
        max_realtime_records: int = REALTIME_DEFAULT_MAX_RECORDS,
        max_route_latency_samples: int = ROUTE_DEFAULT_MAX_LATENCY_SAMPLES,
        key_ttl_seconds: int | None = REDIS_DEFAULT_KEY_TTL_SECONDS,
        connection_settings: RedisConnectionSettings | None = None,
        max_routes_per_snapshot: int | None = None,
        redis_client=None,
        snapshot_cache_ttl_seconds: float | None = None,
    ):
        resolved_connection_settings = connection_settings or RedisConnectionSettings()
        self._now = now or datetime.utcnow
        self._snapshot_cache_ttl_seconds = self._resolve_snapshot_cache_ttl_seconds(
            snapshot_cache_ttl_seconds
        )
        self._apply_realtime_state(
            realtime_window_seconds=realtime_window_seconds,
            realtime_bucket_seconds=realtime_bucket_seconds,
            max_realtime_records=max_realtime_records,
            max_route_latency_samples=max_route_latency_samples,
        )
        namespace_settings = key_namespace_settings or RedisNamespaceSettings()
        self._key_prefix = self._build_key_prefix(namespace_settings)
        self._key_ttl_seconds = self._resolve_optional_positive_int(key_ttl_seconds)
        self._redis = self._create_redis_client(
            redis_client=redis_client,
            connection_settings=resolved_connection_settings,
        )
        self._redis.ping()
        self._max_routes_per_snapshot = self._resolve_optional_positive_int(
            max_routes_per_snapshot
        )
        self._snapshot_cache_expires_at_ms: float | None = None
        self._snapshot_cache: MetricsSnapshot | None = None

    @staticmethod
    def _resolve_snapshot_cache_ttl_seconds(
        snapshot_cache_ttl_seconds: float | None,
    ) -> float:
        parsed_snapshot_cache_ttl_seconds = (
            0.0 if snapshot_cache_ttl_seconds is None else float(snapshot_cache_ttl_seconds)
        )
        return max(0.0, parsed_snapshot_cache_ttl_seconds)

    @staticmethod
    def _build_key_prefix(namespace_settings: RedisNamespaceSettings) -> str:
        base_prefix = (
            str(namespace_settings.key_prefix or REDIS_DEFAULT_KEY_PREFIX).strip()
            or REDIS_DEFAULT_KEY_PREFIX
        )
        namespace_version = (
            str(namespace_settings.key_namespace_version or REDIS_DEFAULT_KEY_NAMESPACE_VERSION).strip()
            or REDIS_DEFAULT_KEY_NAMESPACE_VERSION
        )
        return f"{base_prefix}:{namespace_version}"

    @staticmethod
    def _resolve_optional_positive_int(value: int | None) -> int | None:
        parsed_value = None if value is None else int(value)
        return parsed_value if parsed_value and parsed_value > 0 else None

    @staticmethod
    def _create_redis_client(
        *,
        redis_client,
        connection_settings: RedisConnectionSettings,
    ):
        if redis_client is not None:
            return redis_client
        if redis is None:
            raise RuntimeError(
                "Redis dependency is missing. Install with `pip install redis`."
            )
        return redis.Redis.from_url(
            connection_settings.redis_url,
            decode_responses=True,
            socket_timeout=connection_settings.socket_timeout_seconds,
            socket_connect_timeout=connection_settings.connect_timeout_seconds,
        )

    @property
    def _routes_index_key(self) -> str:
        return f"{self._key_prefix}:routes"

    @property
    def _events_key(self) -> str:
        return f"{self._key_prefix}:events"

    @property
    def _realtime_key(self) -> str:
        return f"{self._key_prefix}:realtime"

    @property
    def _route_rankings_key(self) -> str:
        return f"{self._key_prefix}:routes_by_volume"

    def _route_latency_samples_key(self, route_hash_key: str) -> str:
        return f"{route_hash_key}:latency_samples"

    def _route_hash_key(self, *, route: str, method: str) -> str:
        digest = sha256(
            f"{route}{REDIS_KEY_SEPARATOR}{method}".encode("utf-8")
        ).hexdigest()
        return f"{self._key_prefix}:route:{digest}"

    def record_request(self, event: RequestMetricEvent) -> None:
        self._invalidate_snapshot_cache()
        route, method = self._route_key_from_event(event)
        route_hash_key = self._route_hash_key(route=route, method=method)
        route_latency_samples_key = self._route_latency_samples_key(route_hash_key)
        duration_ms = max(0.0, float(event.duration_ms))
        is_error = 1 if event.status_code >= 500 else 0
        now_epoch = self._realtime_series_builder.to_epoch_seconds(self._now())
        created_epoch = self._realtime_series_builder.to_epoch_seconds(event.created_at)

        pipeline = self._redis.pipeline()
        pipeline.sadd(self._routes_index_key, route_hash_key)
        pipeline.hsetnx(route_hash_key, REDIS_FIELD_ROUTE, route)
        pipeline.hsetnx(route_hash_key, REDIS_FIELD_METHOD, method)
        pipeline.hincrby(route_hash_key, REDIS_FIELD_TOTAL_REQUESTS, 1)
        if is_error:
            pipeline.hincrby(route_hash_key, REDIS_FIELD_TOTAL_ERRORS, 1)
        pipeline.hincrbyfloat(route_hash_key, REDIS_FIELD_TOTAL_LATENCY_MS, duration_ms)
        pipeline.lpush(route_latency_samples_key, duration_ms)
        pipeline.ltrim(route_latency_samples_key, 0, self._max_route_latency_samples - 1)
        pipeline.zadd(
            self._realtime_key,
            {self._encode_realtime_member(is_error=bool(is_error), duration_ms=duration_ms): created_epoch},
        )
        if self._max_routes_per_snapshot is not None:
            pipeline.zincrby(self._route_rankings_key, 1, route_hash_key)
        pipeline.zremrangebyscore(
            self._realtime_key,
            "-inf",
            f"({now_epoch - self._realtime_window_seconds}",
        )
        if self._max_realtime_records > 0:
            pipeline.zremrangebyrank(
                self._realtime_key,
                0,
                -self._max_realtime_records - 1,
            )
        self._queue_set_route_max_latency(
            pipeline=pipeline,
            route_hash_key=route_hash_key,
            duration_ms=duration_ms,
        )
        self._queue_expire(pipeline, self._routes_index_key)
        self._queue_expire(pipeline, route_hash_key)
        self._queue_expire(pipeline, route_latency_samples_key)
        self._queue_expire(pipeline, self._realtime_key)
        if self._max_routes_per_snapshot is not None:
            self._queue_expire(pipeline, self._route_rankings_key)
        pipeline.execute()

    def record_event(self, event: AuthMetricEvent) -> None:
        self._invalidate_snapshot_cache()
        event_name, outcome = self._event_key_from_event(event)
        field = self._event_hash_field(event_name=event_name, outcome=outcome)
        pipeline = self._redis.pipeline()
        pipeline.hincrby(self._events_key, field, 1)
        self._queue_expire(pipeline, self._events_key)
        pipeline.execute()

    def get_snapshot(self) -> MetricsSnapshot:
        now_value = self._now()
        now_epoch = self._realtime_series_builder.to_epoch_seconds(now_value)
        if (
            self._snapshot_cache is not None
            and self._snapshot_cache_expires_at_ms is not None
            and now_epoch <= self._snapshot_cache_expires_at_ms
        ):
            return self._snapshot_cache

        min_epoch = now_epoch - self._realtime_window_seconds

        pipeline = self._redis.pipeline()
        if self._max_routes_per_snapshot is None:
            pipeline.smembers(self._routes_index_key)
        else:
            pipeline.zrevrange(
                self._route_rankings_key,
                0,
                self._max_routes_per_snapshot - 1,
            )
        pipeline.hgetall(self._events_key)
        pipeline.zremrangebyscore(self._realtime_key, "-inf", f"({min_epoch}")
        pipeline.zrangebyscore(self._realtime_key, min_epoch, "+inf", withscores=True)
        route_hash_keys, raw_events, _, raw_realtime = pipeline.execute()

        if self._max_routes_per_snapshot is None:
            route_hash_keys = self._limit_route_hash_keys(route_hash_keys)
        elif not route_hash_keys:
            route_hash_keys = self._limit_route_hash_keys_from_index()
        route_items = self._build_route_items(route_hash_keys)
        event_items = self._build_event_items(raw_events)
        realtime_records = self._build_realtime_records(raw_realtime)
        snapshot = self._build_snapshot_response(
            now_value=now_value,
            route_items=route_items,
            event_items=event_items,
            realtime_records=realtime_records,
        )
        if self._snapshot_cache_ttl_seconds > 0:
            self._snapshot_cache = snapshot
            self._snapshot_cache_expires_at_ms = (
                now_epoch + self._snapshot_cache_ttl_seconds
            )
        else:
            self._snapshot_cache = None
            self._snapshot_cache_expires_at_ms = None
        return snapshot

    def _limit_route_hash_keys_from_index(self) -> list[str]:
        route_hash_keys = self._redis.smembers(self._routes_index_key)
        route_hash_keys = list(route_hash_keys)
        if not route_hash_keys or self._max_routes_per_snapshot is None:
            return route_hash_keys

        pipeline = self._redis.pipeline()
        for route_hash_key in route_hash_keys:
            pipeline.hmget(route_hash_key, REDIS_FIELD_ROUTE, REDIS_FIELD_METHOD)
        route_metadata = pipeline.execute()

        parsed: list[tuple[str, str, str]] = []
        for route_hash_key, raw_metadata in zip(route_hash_keys, route_metadata):
            if isinstance(raw_metadata, (list, tuple)) and len(raw_metadata) >= 2:
                raw_route, raw_method = raw_metadata[0], raw_metadata[1]
            else:
                raw_route, raw_method = None, None
            route = self._normalize_text(raw_route, default=UNKNOWN_ROUTE)
            method = self._normalize_text(
                raw_method,
                default=UNKNOWN_METHOD,
                transform=str.upper,
            )
            parsed.append((route, method, route_hash_key))

        parsed.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[2] for item in parsed][: self._max_routes_per_snapshot]

    def reset(self) -> None:
        self._invalidate_snapshot_cache()
        route_hash_keys = self._redis.smembers(self._routes_index_key)
        keys_to_delete = [
            self._routes_index_key,
            self._events_key,
            self._realtime_key,
            self._route_rankings_key,
        ]
        for route_hash_key in route_hash_keys:
            keys_to_delete.append(route_hash_key)
            keys_to_delete.append(self._route_latency_samples_key(route_hash_key))
        self._redis.delete(*keys_to_delete)

    def _queue_set_route_max_latency(
        self,
        *,
        pipeline,
        route_hash_key: str,
        duration_ms: float,
    ) -> None:
        script = """
            local current = tonumber(redis.call('HGET', KEYS[1], ARGV[1]))
            local candidate = tonumber(ARGV[2])
            if not candidate then
                return 0
            end
            if not current or candidate > current then
                redis.call('HSET', KEYS[1], ARGV[1], candidate)
                return 1
            end
            return 0
        """
        pipeline.eval(script, 1, route_hash_key, REDIS_FIELD_MAX_LATENCY_MS, duration_ms)

    def _invalidate_snapshot_cache(self) -> None:
        self._snapshot_cache = None
        self._snapshot_cache_expires_at_ms = None

    def _trim_realtime_records(self) -> None:
        current_size = self._to_int(self._redis.zcard(self._realtime_key))
        overflow = current_size - self._max_realtime_records
        if overflow > 0:
            self._redis.zremrangebyrank(self._realtime_key, 0, overflow - 1)

    def _trim_route_latency_samples(self, *, route_latency_samples_key: str) -> None:
        current_size = self._to_int(self._redis.llen(route_latency_samples_key))
        overflow = current_size - self._max_route_latency_samples
        if overflow > 0:
            self._redis.ltrim(
                route_latency_samples_key,
                0,
                self._max_route_latency_samples - 1,
            )

    def _queue_expire(self, pipeline, key: str) -> None:
        if self._key_ttl_seconds is None:
            return
        pipeline.expire(key, self._key_ttl_seconds)

    def _build_route_items(
        self,
        route_hash_keys: Iterable[str],
    ) -> list[tuple[tuple[str, str], _RouteAccumulator]]:
        route_hash_keys = list(route_hash_keys)
        if not route_hash_keys:
            return []

        pipeline = self._redis.pipeline()
        for route_hash_key in route_hash_keys:
            pipeline.hmget(route_hash_key, *_REDIS_ROUTE_SNAPSHOT_FIELDS)
            pipeline.lrange(
                self._route_latency_samples_key(route_hash_key),
                0,
                self._max_route_latency_samples - 1,
            )
        route_data = pipeline.execute()

        items: list[tuple[tuple[str, str], _RouteAccumulator]] = []
        for index, route_hash_key in enumerate(route_hash_keys):
            raw_route = route_data[index * 2]
            raw_latency_samples = route_data[index * 2 + 1]
            if not isinstance(raw_route, list):
                continue
            raw_route_values = list(raw_route)
            (
                route_raw,
                method_raw,
                total_requests_raw,
                total_errors_raw,
                total_latency_ms_raw,
                max_latency_ms_raw,
            ) = (
                raw_route_values + [None] * (6 - len(raw_route_values))
            )[:6]
            route = self._normalize_text(route_raw, default=UNKNOWN_ROUTE)
            method = self._normalize_text(
                method_raw,
                default=UNKNOWN_METHOD,
                transform=str.upper,
            )
            p95_latency_ms, p99_latency_ms = self._resolve_latency_percentiles_from_samples(
                raw_latency_samples
            )
            accumulator = _RouteAccumulator(
                total_requests=self._to_int(total_requests_raw),
                total_errors=self._to_int(total_errors_raw),
                total_latency_ms=self._to_float(total_latency_ms_raw),
                max_latency_ms=self._to_float(max_latency_ms_raw),
                max_latency_samples=self._max_route_latency_samples,
                precomputed_p95_latency_ms=p95_latency_ms,
                precomputed_p99_latency_ms=p99_latency_ms,
            )
            items.append(((route, method), accumulator))
        return items

    def _limit_route_hash_keys(
        self,
        route_hash_keys: Iterable[str],
    ) -> list[str]:
        route_hash_keys_list = list(route_hash_keys)
        if not route_hash_keys_list or self._max_routes_per_snapshot is None:
            return route_hash_keys_list
        route_hash_keys_list = sorted(route_hash_keys_list)
        return route_hash_keys_list[: self._max_routes_per_snapshot]

    def _build_event_items(
        self,
        raw_events: dict[str, str],
    ) -> list[tuple[tuple[str, str], int]]:
        items: list[tuple[tuple[str, str], int]] = []
        for event_field, count_raw in raw_events.items():
            event_name, outcome = self._parse_event_hash_field(event_field)
            count = self._to_int(count_raw)
            items.append(((event_name, outcome), count))
        return items

    def _build_realtime_records(
        self,
        raw_realtime: list[tuple[str, float]],
    ) -> list[_RealtimeRequestRecord]:
        records: list[_RealtimeRequestRecord] = []
        for member, score in raw_realtime:
            is_error, duration_ms = self._decode_realtime_member(member)
            records.append(
                _RealtimeRequestRecord(
                    created_at=self._realtime_series_builder.utc_datetime_from_epoch(float(score)),
                    is_error=is_error,
                    duration_ms=duration_ms,
                )
            )
        return records

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _resolve_latency_percentiles_from_samples(
        cls,
        raw_samples: Iterable[object],
    ) -> tuple[float, float]:
        samples = [cls._to_float(sample) for sample in raw_samples]
        samples = [max(0.0, sample) for sample in samples]
        if not samples:
            return 0.0, 0.0
        sorted_samples = sorted(samples)
        return (
            _RouteAccumulator._percentile(
                sorted_samples=sorted_samples,
                percentile=0.95,
            ),
            _RouteAccumulator._percentile(
                sorted_samples=sorted_samples,
                percentile=0.99,
            ),
        )

    @staticmethod
    def _event_hash_field(*, event_name: str, outcome: str) -> str:
        return f"{event_name}{REDIS_KEY_SEPARATOR}{outcome}"

    @staticmethod
    def _parse_event_hash_field(field: str) -> tuple[str, str]:
        if REDIS_KEY_SEPARATOR not in field:
            return UNKNOWN_VALUE, UNKNOWN_VALUE
        event_name, outcome = field.split(REDIS_KEY_SEPARATOR, 1)
        return (
            event_name or UNKNOWN_VALUE,
            outcome or UNKNOWN_VALUE,
        )

    @staticmethod
    def _encode_realtime_member(*, is_error: bool, duration_ms: float) -> str:
        return (
            f"{uuid4().hex}"
            f"{REDIS_KEY_SEPARATOR}{1 if is_error else 0}"
            f"{REDIS_KEY_SEPARATOR}{duration_ms:.6f}"
        )

    @staticmethod
    def _decode_realtime_member(member: str) -> tuple[bool, float]:
        parts = member.split(REDIS_KEY_SEPARATOR, 2)
        if len(parts) != 3:
            return False, 0.0
        return parts[1] == "1", RedisMetricsRepository._to_float(parts[2])
