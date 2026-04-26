from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from monitoring.entities import AuthMetricEvent, RequestMetricEvent
from monitoring.infrastructure.repositories import (
    _build_realtime_series_config,
    _MetricKeyNormalizerMixin,
    _RealtimeSeriesBuilder,
    _RealtimeRequestRecord,
    _RouteAccumulator,
    RedisNamespaceSettings,
    RedisConnectionSettings,
    _SnapshotFactory,
    _REDIS_ROUTE_SNAPSHOT_FIELDS,
    REDIS_KEY_SEPARATOR,
    RedisMetricsRepository,
)
from monitoring.repositories import (
    InMemoryMetricsRepository,
    ResilientMetricsRepository,
)


class RouteAccumulatorTest(SimpleTestCase):
    def test_to_snapshot_uses_zero_average_when_no_requests(self):
        accumulator = _RouteAccumulator()
        snapshot = accumulator.to_snapshot(route="/health", method="GET")

        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.avg_latency_ms, 0.0)
        self.assertEqual(snapshot.max_latency_ms, 0.0)
        self.assertEqual(snapshot.p95_latency_ms, 0.0)
        self.assertEqual(snapshot.p99_latency_ms, 0.0)


class SnapshotFactoryTest(SimpleTestCase):
    def test_build_realtime_series_config_clamps_values(self):
        config = _build_realtime_series_config(
            realtime_window_seconds=0,
            realtime_bucket_seconds=15,
            max_realtime_records=0,
        )

        self.assertEqual(config.window_seconds, 1)
        self.assertEqual(config.bucket_seconds, 1)
        self.assertEqual(config.max_records, 1)

    def test_realtime_series_builder_handles_aware_and_naive_datetimes(self):
        builder = _RealtimeSeriesBuilder(
            window_seconds=20,
            bucket_seconds=10,
        )
        naive = datetime(2026, 4, 20, 10, 0, 0)
        aware = datetime(
            2026,
            4,
            20,
            10,
            0,
            0,
            tzinfo=timezone.utc,
        )
        epoch = builder.to_epoch_seconds(aware)

        self.assertEqual(
            builder.to_epoch_seconds(aware),
            builder.to_epoch_seconds(naive),
        )

        target = builder.utc_datetime_from_epoch(epoch)
        self.assertEqual(
            target,
            datetime(2026, 4, 20, 10, 0, 0),
        )
        self.assertEqual(builder.window_seconds, 20)
        self.assertEqual(builder.bucket_seconds, 10)

    def test_percentile_bounds_are_clamped(self):
        self.assertEqual(_RouteAccumulator._percentile(sorted_samples=[], percentile=0.5), 0.0)
        self.assertEqual(_RouteAccumulator._percentile(sorted_samples=[10.0, 20.0], percentile=2.0), 20.0)
        self.assertEqual(_RouteAccumulator._percentile(sorted_samples=[10.0, 20.0], percentile=-1.0), 10.0)

    def test_snapshot_factory_orders_routes_and_events_consistently(self):
        route_one = _RouteAccumulator()
        route_two = _RouteAccumulator()
        route_one.total_requests = 1
        route_two.total_requests = 2
        route_one.max_latency_ms = 100.0
        route_two.max_latency_ms = 50.0

        routes = _SnapshotFactory.build_route_snapshots(
            [
                (("/a", "GET"), route_one),
                (("/b", "POST"), route_two),
            ]
        )

        self.assertEqual(routes[0].route, "/b")
        self.assertEqual(routes[1].route, "/a")

        events = _SnapshotFactory.build_event_snapshots(
            [
                (("login", "success"), 1),
                (("register", "success"), 2),
            ]
        )
        self.assertEqual(events[0].event_name, "register")
        self.assertEqual(events[1].event_name, "login")


class MetricKeyNormalizerMixinTest(SimpleTestCase):
    def test_normalize_text_handles_bytes_input(self):
        value = _MetricKeyNormalizerMixin._normalize_text(
            b"  /monitoring  ",
            default="unknown",
        )

        self.assertEqual(value, "/monitoring")

    def test_normalize_text_handles_non_string_input(self):
        value = _MetricKeyNormalizerMixin._normalize_text(
            401,
            default="unknown",
        )

        self.assertEqual(value, "401")


class InMemoryMetricsRepositoryTest(SimpleTestCase):
    def setUp(self):
        self.repo = InMemoryMetricsRepository(
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
        )

    def _event(
        self,
        *,
        route="/upload",
        method="POST",
        status_code=200,
        duration_ms=120.0,
        created_at=None,
    ):
        return RequestMetricEvent(
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            created_at=created_at or datetime(2026, 4, 20, 11, 59, 0),
        )

    def _auth_event(
        self,
        *,
        event_name="login",
        outcome="success",
        endpoint="/auth/login/",
    ):
        return AuthMetricEvent(
            event_name=event_name,
            outcome=outcome,
            endpoint=endpoint,
            created_at=datetime(2026, 4, 20, 11, 59, 0),
        )

    def test_get_snapshot_returns_empty_totals_when_no_data(self):
        snapshot = self.repo.get_snapshot()

        self.assertEqual(snapshot.generated_at, datetime(2026, 4, 20, 12, 0, 0))
        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.total_errors, 0)
        self.assertEqual(snapshot.routes, ())
        self.assertEqual(snapshot.events, ())
        self.assertEqual(snapshot.timeseries_window_seconds, 60)
        self.assertEqual(snapshot.timeseries_bucket_seconds, 10)
        self.assertEqual(len(snapshot.timeseries), 6)
        self.assertTrue(all(point.requests == 0 for point in snapshot.timeseries))
        self.assertEqual(
            snapshot.timeseries[0].timestamp,
            datetime(2026, 4, 20, 11, 59, 10),
        )
        self.assertEqual(
            snapshot.timeseries[-1].timestamp,
            datetime(2026, 4, 20, 12, 0, 0),
        )

    def test_record_request_aggregates_totals_and_errors(self):
        self.repo.record_request(self._event(status_code=200, duration_ms=100.0))
        self.repo.record_request(self._event(status_code=502, duration_ms=300.0))

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 2)
        self.assertEqual(snapshot.total_errors, 1)
        self.assertEqual(len(snapshot.routes), 1)
        route = snapshot.routes[0]
        self.assertEqual(route.route, "/upload")
        self.assertEqual(route.method, "POST")
        self.assertEqual(route.total_requests, 2)
        self.assertEqual(route.total_errors, 1)
        self.assertEqual(route.avg_latency_ms, 200.0)
        self.assertEqual(route.max_latency_ms, 300.0)
        self.assertEqual(route.p95_latency_ms, 300.0)
        self.assertEqual(route.p99_latency_ms, 300.0)
        self.assertEqual(
            sum(point.requests for point in snapshot.timeseries),
            2,
        )
        self.assertEqual(
            sum(point.errors for point in snapshot.timeseries),
            1,
        )

    def test_record_request_normalizes_empty_route_and_method(self):
        self.repo.record_request(self._event(route=" ", method=" ", duration_ms=10.0))

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.routes[0].route, "unknown")
        self.assertEqual(snapshot.routes[0].method, "UNKNOWN")

    def test_record_request_clamps_negative_duration_to_zero(self):
        self.repo.record_request(self._event(duration_ms=-10.0))

        route = self.repo.get_snapshot().routes[0]
        self.assertEqual(route.avg_latency_ms, 0.0)
        self.assertEqual(route.max_latency_ms, 0.0)

    def test_get_snapshot_sorts_by_total_requests_then_route_method(self):
        self.repo.record_request(self._event(route="/b", method="GET", duration_ms=1.0))
        self.repo.record_request(self._event(route="/a", method="GET", duration_ms=1.0))
        self.repo.record_request(self._event(route="/b", method="GET", duration_ms=1.0))

        routes = self.repo.get_snapshot().routes
        self.assertEqual([item.route for item in routes], ["/b", "/a"])

    def test_reset_clears_accumulated_metrics(self):
        self.repo.record_request(self._event())
        self.repo.record_event(self._auth_event())
        self.repo.reset()

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 0)
        self.assertEqual(snapshot.routes, ())
        self.assertEqual(snapshot.events, ())

    def test_record_event_aggregates_event_counters(self):
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))
        self.repo.record_event(self._auth_event(event_name="login", outcome="client_error"))

        snapshot = self.repo.get_snapshot()
        events = snapshot.to_dict()["events"]
        self.assertEqual(events["login"]["success"], 2)
        self.assertEqual(events["login"]["client_error"], 1)

    def test_record_event_normalizes_empty_name_and_outcome(self):
        self.repo.record_event(self._auth_event(event_name=" ", outcome=" "))

        snapshot = self.repo.get_snapshot()
        events = snapshot.to_dict()["events"]
        self.assertEqual(events["unknown"]["unknown"], 1)

    def test_get_snapshot_sorts_events_by_count_then_name_and_outcome(self):
        self.repo.record_event(self._auth_event(event_name="register", outcome="success"))
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))

        events = self.repo.get_snapshot().events
        self.assertEqual(
            [(item.event_name, item.outcome, item.count) for item in events],
            [("login", "success", 2), ("register", "success", 1)],
        )

    def test_route_percentile_uses_bounded_recent_samples(self):
        repo = InMemoryMetricsRepository(
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            max_route_latency_samples=3,
        )
        repo.record_request(self._event(duration_ms=10.0))
        repo.record_request(self._event(duration_ms=20.0))
        repo.record_request(self._event(duration_ms=30.0))
        repo.record_request(self._event(duration_ms=100.0))

        route = repo.get_snapshot().routes[0]
        self.assertEqual(route.max_latency_ms, 100.0)
        self.assertEqual(route.p95_latency_ms, 100.0)
        self.assertEqual(route.p99_latency_ms, 100.0)

    def test_realtime_bucket_clamps_high_index_when_record_is_recent_edge(self):
        repo = InMemoryMetricsRepository(
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            realtime_window_seconds=20,
            realtime_bucket_seconds=10,
            max_route_latency_samples=10,
            max_realtime_records=10,
        )
        builder = repo._realtime_series_builder
        record = _RealtimeRequestRecord(
            created_at=builder.utc_datetime_from_epoch(201.0),
            is_error=False,
            duration_ms=10.0,
        )
        now_epoch = 200.0
        points = builder.build_points(records=(record,), now_epoch=now_epoch)

        self.assertEqual(points[-1].requests, 1)

    def test_realtime_bucket_discards_records_outside_window(self):
        repo = InMemoryMetricsRepository(
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            realtime_window_seconds=20,
            realtime_bucket_seconds=10,
            max_route_latency_samples=10,
            max_realtime_records=10,
        )
        builder = repo._realtime_series_builder
        record = _RealtimeRequestRecord(
            created_at=builder.utc_datetime_from_epoch(179.0),
            is_error=False,
            duration_ms=10.0,
        )
        now_epoch = 200.0

        points = builder.build_points(records=(record,), now_epoch=now_epoch)
        self.assertTrue(all(point.requests == 0 for point in points))

    def test_recent_requests_prunes_when_capacity_exceeded(self):
        repo = InMemoryMetricsRepository(
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            max_realtime_records=1,
        )
        repo.record_request(self._event(created_at=datetime(2026, 4, 20, 11, 59, 50)))
        repo.record_request(self._event(created_at=datetime(2026, 4, 20, 11, 59, 59)))

        self.assertEqual(len(repo._recent_requests), 1)
        self.assertEqual(repo._recent_requests[0].duration_ms, 120.0)

    def test_timeseries_excludes_requests_older_than_window(self):
        self.repo.record_request(
            self._event(
                created_at=datetime(2026, 4, 20, 11, 58, 0),
                duration_ms=50.0,
            )
        )

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 1)
        self.assertEqual(
            sum(point.requests for point in snapshot.timeseries),
            0,
        )


class _FakeRedisPipeline:
    def __init__(self, client):
        self._client = client
        self._operations = []

    def _queue(self, method_name, *args, **kwargs):
        self._operations.append((method_name, args, kwargs))
        return self

    def execute(self):
        results = []
        for method_name, args, kwargs in self._operations:
            method = getattr(self._client, method_name)
            results.append(method(*args, **kwargs))
        self._operations = []
        return results

    def sadd(self, *args, **kwargs):
        return self._queue("sadd", *args, **kwargs)

    def hsetnx(self, *args, **kwargs):
        return self._queue("hsetnx", *args, **kwargs)

    def hincrby(self, *args, **kwargs):
        return self._queue("hincrby", *args, **kwargs)

    def hincrbyfloat(self, *args, **kwargs):
        return self._queue("hincrbyfloat", *args, **kwargs)

    def zadd(self, *args, **kwargs):
        return self._queue("zadd", *args, **kwargs)

    def zincrby(self, *args, **kwargs):
        return self._queue("zincrby", *args, **kwargs)

    def zrevrange(self, *args, **kwargs):
        return self._queue("zrevrange", *args, **kwargs)

    def zremrangebyscore(self, *args, **kwargs):
        return self._queue("zremrangebyscore", *args, **kwargs)

    def zremrangebyrank(self, *args, **kwargs):
        return self._queue("zremrangebyrank", *args, **kwargs)

    def smembers(self, *args, **kwargs):
        return self._queue("smembers", *args, **kwargs)

    def hgetall(self, *args, **kwargs):
        return self._queue("hgetall", *args, **kwargs)

    def zrangebyscore(self, *args, **kwargs):
        return self._queue("zrangebyscore", *args, **kwargs)

    def hmget(self, *args, **kwargs):
        return self._queue("hmget", *args, **kwargs)

    def eval(self, *args, **kwargs):
        return self._queue("eval", *args, **kwargs)

    def lpush(self, *args, **kwargs):
        return self._queue("lpush", *args, **kwargs)

    def ltrim(self, *args, **kwargs):
        return self._queue("ltrim", *args, **kwargs)

    def lrange(self, *args, **kwargs):
        return self._queue("lrange", *args, **kwargs)

    def expire(self, *args, **kwargs):
        return self._queue("expire", *args, **kwargs)


class _FakeRedisClient:
    def __init__(self):
        self._sets = {}
        self._hashes = {}
        self._zsets = {}
        self._lists = {}
        self._expirations = {}

    def ping(self):
        return True

    def pipeline(self):
        return _FakeRedisPipeline(self)

    def sadd(self, key, *members):
        values = self._sets.setdefault(key, set())
        added = 0
        for member in members:
            if member not in values:
                values.add(member)
                added += 1
        return added

    def smembers(self, key):
        return set(self._sets.get(key, set()))

    def hsetnx(self, key, field, value):
        table = self._hashes.setdefault(key, {})
        if field in table:
            return 0
        table[field] = str(value)
        return 1

    def hset(self, key, field, value):
        table = self._hashes.setdefault(key, {})
        table[field] = str(value)
        return 1

    def hget(self, key, field):
        return self._hashes.get(key, {}).get(field)

    def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    def hmget(self, key, *fields):
        table = self._hashes.setdefault(key, {})
        return [table.get(field) for field in fields]

    def hincrby(self, key, field, amount):
        table = self._hashes.setdefault(key, {})
        current = int(table.get(field, "0"))
        updated = current + int(amount)
        table[field] = str(updated)
        return updated

    def hincrbyfloat(self, key, field, amount):
        table = self._hashes.setdefault(key, {})
        current = float(table.get(field, "0"))
        updated = current + float(amount)
        table[field] = str(updated)
        return updated

    def zadd(self, key, mapping):
        zset = self._zsets.setdefault(key, [])
        added = 0
        for member, score in mapping.items():
            zset[:] = [item for item in zset if item[1] != member]
            zset.append((float(score), member))
            added += 1
        zset.sort(key=lambda item: (item[0], item[1]))
        return added

    def zincrby(self, key, amount, member):
        zset = self._zsets.setdefault(key, [])
        increment = float(amount)
        found = False
        for index, (score, current_member) in enumerate(zset):
            if current_member == member:
                zset[index] = (score + increment, current_member)
                found = True
                break
        if not found:
            zset.append((increment, member))
        zset.sort(key=lambda item: (item[0], item[1]))
        return self.zscore(key, member)

    def zscore(self, key, member):
        for score, current_member in self._zsets.get(key, []):
            if current_member == member:
                return score
        return None

    def zrevrange(self, key, start, stop, withscores=False):
        zset = sorted(
            self._zsets.get(key, []),
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
        if not zset:
            return []
        if start < 0:
            start = max(len(zset) + start, 0)
        if stop < 0:
            stop = len(zset) + stop
        stop = min(stop, len(zset) - 1)
        if start > stop:
            return []
        selected = zset[start : stop + 1]
        if withscores:
            return selected
        return [member for _, member in selected]

    @staticmethod
    def _score_matches(score, min_score, max_score):
        min_inclusive = True
        max_inclusive = True
        if isinstance(min_score, str) and min_score.startswith("("):
            min_inclusive = False
            min_score = min_score[1:]
        if isinstance(max_score, str) and max_score.startswith("("):
            max_inclusive = False
            max_score = max_score[1:]

        min_value = float("-inf") if min_score in ("-inf", "-INF") else float(min_score)
        max_value = float("inf") if max_score in ("+inf", "inf", "+INF", "INF") else float(max_score)

        if min_inclusive:
            min_ok = score >= min_value
        else:
            min_ok = score > min_value
        if max_inclusive:
            max_ok = score <= max_value
        else:
            max_ok = score < max_value
        return min_ok and max_ok

    def zremrangebyscore(self, key, min_score, max_score):
        zset = self._zsets.get(key, [])
        before = len(zset)
        zset[:] = [
            item
            for item in zset
            if not self._score_matches(item[0], min_score, max_score)
        ]
        return before - len(zset)

    def zrangebyscore(self, key, min_score, max_score, withscores=False):
        zset = self._zsets.get(key, [])
        filtered = [
            item for item in zset if self._score_matches(item[0], min_score, max_score)
        ]
        if withscores:
            return [(member, score) for score, member in filtered]
        return [member for score, member in filtered]

    def eval(self, script, numkeys, *keys_and_args):
        if "redis.call('HGET'" in script:
            key = keys_and_args[0]
            field = keys_and_args[1]
            candidate = float(keys_and_args[2])
            current_raw = self._hashes.get(key, {}).get(field)
            current = float(current_raw) if current_raw is not None else None
            if current is None or candidate > current:
                self._hashes.setdefault(key, {})[field] = str(candidate)
        return None

    def zcard(self, key):
        return len(self._zsets.get(key, []))

    def zremrangebyrank(self, key, start, stop):
        zset = self._zsets.get(key, [])
        if not zset:
            return 0
        if start < 0:
            start = max(len(zset) + start, 0)
        if stop < 0:
            stop = len(zset) + stop
        stop = min(stop, len(zset) - 1)
        if start > stop:
            return 0
        removed_count = stop - start + 1
        del zset[start : stop + 1]
        return removed_count

    def lpush(self, key, *values):
        items = self._lists.setdefault(key, [])
        for value in values:
            items.insert(0, str(value))
        return len(items)

    def ltrim(self, key, start, stop):
        items = self._lists.get(key, [])
        if not items:
            return True
        if start < 0:
            start = max(len(items) + start, 0)
        if stop < 0:
            stop = len(items) + stop
        stop = min(stop, len(items) - 1)
        if start > stop:
            self._lists[key] = []
            return True
        self._lists[key] = items[start : stop + 1]
        return True

    def lrange(self, key, start, stop):
        items = self._lists.get(key, [])
        if not items:
            return []
        if start < 0:
            start = max(len(items) + start, 0)
        if stop < 0:
            stop = len(items) + stop
        stop = min(stop, len(items) - 1)
        if start > stop:
            return []
        return list(items[start : stop + 1])

    def llen(self, key):
        return len(self._lists.get(key, []))

    def expire(self, key, ttl_seconds):
        self._expirations[key] = int(ttl_seconds)
        return 1

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self._sets:
                del self._sets[key]
                removed += 1
            if key in self._hashes:
                del self._hashes[key]
                removed += 1
            if key in self._zsets:
                del self._zsets[key]
                removed += 1
            if key in self._lists:
                del self._lists[key]
                removed += 1
            if key in self._expirations:
                del self._expirations[key]
        return removed


class RedisMetricsRepositoryInternalTest(SimpleTestCase):
    def setUp(self):
        self.repo = RedisMetricsRepository(
            redis_client=Mock(),
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
        )

    def test_decode_realtime_member_invalid_payload(self):
        is_error, duration_ms = self.repo._decode_realtime_member("invalid")

        self.assertFalse(is_error)
        self.assertEqual(duration_ms, 0.0)

    def test_encode_and_decode_realtime_member_round_trip(self):
        member = self.repo._encode_realtime_member(is_error=True, duration_ms=12.5)
        is_error, duration_ms = self.repo._decode_realtime_member(member)

        self.assertTrue(is_error)
        self.assertAlmostEqual(duration_ms, 12.5, places=4)

    def test_build_route_items_skips_non_dict_payload(self):
        pipeline = Mock()
        pipeline.hmget.return_value = pipeline
        pipeline.lrange.return_value = pipeline
        pipeline.execute.return_value = [None, []]
        self.repo._redis.pipeline = Mock(return_value=pipeline)

        items = self.repo._build_route_items(["route-key"])

        self.assertEqual(items, [])
        pipeline.hmget.assert_called_once_with("route-key", *_REDIS_ROUTE_SNAPSHOT_FIELDS)

    def test_record_request_does_not_run_separate_trim_commands(self):
        redis_client = Mock()
        redis_client.pipeline.return_value = pipeline = Mock()
        pipeline.execute.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
        )

        repository.record_request(
            RequestMetricEvent(
                route="/upload",
                method="POST",
                status_code=200,
                duration_ms=110.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )

        self.assertEqual(redis_client.hget.call_count, 0)
        self.assertEqual(redis_client.llen.call_count, 0)
        self.assertEqual(redis_client.zcard.call_count, 0)
        self.assertEqual(redis_client.zremrangebyrank.call_count, 0)
        self.assertEqual(redis_client.ltrim.call_count, 0)
        pipeline.zremrangebyrank.assert_called_once_with(
            repository._realtime_key,
            0,
            -repository._max_realtime_records - 1,
        )
        pipeline.eval.assert_called_once()

    def test_record_request_skips_route_ranking_commands_when_not_configured(self):
        redis_client = Mock()
        redis_client.pipeline.return_value = pipeline = Mock()
        pipeline.execute.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
        )

        repository.record_request(
            RequestMetricEvent(
                route="/monitoring",
                method="GET",
                status_code=200,
                duration_ms=120.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )

        pipeline.zincrby.assert_not_called()

    def test_record_request_records_route_ranking_when_limit_configured(self):
        redis_client = Mock()
        redis_client.pipeline.return_value = pipeline = Mock()
        pipeline.execute.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
            max_routes_per_snapshot=3,
        )

        repository.record_request(
            RequestMetricEvent(
                route="/monitoring",
                method="GET",
                status_code=200,
                duration_ms=120.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )

        pipeline.zincrby.assert_called_once_with(
            repository._route_rankings_key,
            1,
            repository._route_hash_key(route="/monitoring", method="GET"),
        )

    def test_record_request_skips_realtime_capacity_trim_when_limit_zero(self):
        redis_client = Mock()
        redis_client.pipeline.return_value = pipeline = Mock()
        pipeline.execute.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
        )
        repository._max_realtime_records = 0

        repository.record_request(
            RequestMetricEvent(
                route="/upload",
                method="POST",
                status_code=200,
                duration_ms=110.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )

        pipeline.zremrangebyrank.assert_not_called()

    def test_limit_route_hash_keys_from_index_returns_empty_when_index_is_empty(self):
        redis_client = Mock()
        redis_client.smembers.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
            max_routes_per_snapshot=2,
        )

        self.assertEqual(repository._limit_route_hash_keys_from_index(), [])
        redis_client.pipeline.assert_not_called()

    def test_limit_route_hash_keys_from_index_handles_invalid_metadata_values(self):
        redis_client = Mock()
        redis_client.smembers.return_value = ["route-a", "route-b"]
        redis_client.pipeline.return_value = pipeline = Mock()
        pipeline.execute.return_value = [
            ["/beta", "post"],
            "broken",
        ]
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
            max_routes_per_snapshot=2,
        )

        route_hash_keys = repository._limit_route_hash_keys_from_index()

        self.assertEqual(route_hash_keys, ["route-a", "route-b"])
        self.assertEqual(
            pipeline.hmget.call_count,
            2,
        )
        pipeline.hmget.assert_has_calls(
            [
                call("route-a", "route", "method"),
                call("route-b", "route", "method"),
            ],
            any_order=True,
        )

    def test_limit_route_hash_keys_respects_snapshot_limit(self):
        repository = RedisMetricsRepository(
            redis_client=Mock(),
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=10,
            max_route_latency_samples=4,
            max_routes_per_snapshot=2,
        )
        route_hash_keys = repository._limit_route_hash_keys(["route-c", "route-a", "route-b"])

        self.assertEqual(route_hash_keys, ["route-a", "route-b"])

    def test_snapshot_limits_routes_by_traffic_rank_when_limit_is_configured(self):
        repository = RedisMetricsRepository(
            redis_client=_FakeRedisClient(),
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
            max_routes_per_snapshot=2,
        )

        route_events = [
            ("/a", 1),
            ("/b", 5),
            ("/c", 3),
        ]
        for route, count in route_events:
            for _ in range(count):
                repository.record_request(
                    RequestMetricEvent(
                        route=route,
                        method="GET",
                        status_code=200,
                        duration_ms=10.0,
                        created_at=datetime(2026, 4, 20, 11, 59, 0),
                    )
                )

        snapshot = repository.get_snapshot()

        self.assertEqual([(route.route, route.total_requests) for route in snapshot.routes], [
            ("/b", 5),
            ("/c", 3),
        ])

    def test_get_snapshot_falls_back_to_route_index_when_ranking_set_is_empty(self):
        repository = RedisMetricsRepository(
            redis_client=_FakeRedisClient(),
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=120,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
            max_routes_per_snapshot=2,
        )
        repository.record_request(
            RequestMetricEvent(
                route="/b",
                method="GET",
                status_code=200,
                duration_ms=10.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )
        repository.record_request(
            RequestMetricEvent(
                route="/a",
                method="GET",
                status_code=200,
                duration_ms=10.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )
        repository.record_request(
            RequestMetricEvent(
                route="/c",
                method="GET",
                status_code=200,
                duration_ms=10.0,
                created_at=datetime(2026, 4, 20, 11, 59, 0),
            )
        )

        repository._redis._zsets[repository._route_rankings_key] = []

        snapshot = repository.get_snapshot()

        self.assertEqual(
            [route.route for route in snapshot.routes],
            ["/a", "/b"],
        )

    def test_to_float_returns_default_on_non_numeric(self):
        self.assertEqual(self.repo._to_float("not-number"), 0.0)
        self.assertEqual(self.repo._to_float({}, default=5.5), 5.5)

    def test_to_float_returns_default_on_none_value(self):
        self.assertEqual(self.repo._to_float(None), 0.0)

    def test_to_int_returns_default_on_non_numeric(self):
        self.assertEqual(self.repo._to_int("not-number"), 0)
        self.assertEqual(self.repo._to_int({}, default=10), 10)

    def test_build_realtime_records_keeps_invalid_members(self):
        records = self.repo._build_realtime_records([("broken", 1713607200.0)])

        self.assertEqual(len(records), 1)
        self.assertFalse(records[0].is_error)
        self.assertEqual(records[0].duration_ms, 0.0)

    def test_build_realtime_records_keeps_invalid_members_and_parses_score(self):
        sep = REDIS_KEY_SEPARATOR
        records = self.repo._build_realtime_records(
            [
                (f"c3cf{sep}1{sep}12.500000", 1713607200.5),
                ("invalid|tuple", 1713607201.5),
                (f"9a1d{sep}0{sep}9.250000", 1713607202.0),
            ]
        )

        self.assertEqual(len(records), 3)
        self.assertTrue(records[0].is_error)
        self.assertAlmostEqual(records[0].duration_ms, 12.5, places=4)
        self.assertFalse(records[1].is_error)
        self.assertEqual(records[1].duration_ms, 0.0)
        self.assertFalse(records[2].is_error)
        self.assertAlmostEqual(records[2].duration_ms, 9.25, places=4)

    def test_trim_functions_skip_if_not_overflow(self):
        redis_mock = self.repo._redis
        redis_mock.zcard.return_value = 5
        redis_mock.llen.return_value = 3
        self.repo._trim_realtime_records()
        self.repo._trim_route_latency_samples(route_latency_samples_key="route:latency")
        redis_mock.zremrangebyrank.assert_not_called()
        redis_mock.ltrim.assert_not_called()

    def test_queue_expire_respects_disabled_ttl(self):
        pipeline = Mock()
        original_ttl = self.repo._key_ttl_seconds
        self.repo._key_ttl_seconds = None
        self.repo._queue_expire(pipeline, "example-key")
        pipeline.expire.assert_not_called()

        self.repo._key_ttl_seconds = original_ttl
        self.repo._queue_expire(pipeline, "example-key")
        pipeline.expire.assert_called_once_with("example-key", original_ttl)

    def test_trim_functions_trim_when_over_capacity(self):
        self.repo._redis.zcard.return_value = 25
        self.repo._redis.llen.return_value = 6
        self.repo._max_realtime_records = 10
        self.repo._max_route_latency_samples = 4

        self.repo._trim_realtime_records()
        self.repo._trim_route_latency_samples(route_latency_samples_key="route:latency")

        self.repo._redis.zremrangebyrank.assert_called_once_with(
            self.repo._realtime_key,
            0,
            14,
        )
        self.repo._redis.ltrim.assert_called_once_with(
            "route:latency",
            0,
            3,
        )

    def test_reset_skips_delete_when_no_keys_exist(self):
        redis_client = Mock()
        redis_client.smembers.return_value = []
        repository = RedisMetricsRepository(
            redis_client=redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_ttl_seconds=3600,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
        )

        repository.reset()
        redis_client.delete.assert_called_once_with(
            "monitoring:v1:routes",
            "monitoring:v1:events",
            "monitoring:v1:realtime",
            "monitoring:v1:routes_by_volume",
        )

    def test_trim_functions_skip_when_not_over_capacity(self):
        self.repo._redis.zcard.return_value = 4
        self.repo._redis.llen.return_value = 2
        self.repo._max_realtime_records = 10
        self.repo._max_route_latency_samples = 4

        self.repo._trim_realtime_records()
        self.repo._trim_route_latency_samples(route_latency_samples_key="route:latency")

        self.repo._redis.zremrangebyrank.assert_not_called()
        self.repo._redis.ltrim.assert_not_called()

    def test_init_uses_redis_url_when_client_not_provided(self):
        redis_module = Mock()
        redis_client = Mock()
        redis_module.Redis.from_url.return_value = redis_client

        with patch("monitoring.infrastructure.repositories.redis", redis_module):
            repository = RedisMetricsRepository(
                now=lambda: datetime(2026, 4, 20, 12, 0, 0),
                key_ttl_seconds=None,
                realtime_window_seconds=60,
                realtime_bucket_seconds=10,
                max_realtime_records=100,
                max_route_latency_samples=4,
            )

        redis_module.Redis.from_url.assert_called_once_with(
            "redis://127.0.0.1:6379/0",
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        redis_client.ping.assert_called_once()
        self.assertIs(repository._redis, redis_client)

    @patch("monitoring.infrastructure.repositories.redis", new=None)
    def test_repository_init_raises_when_redis_is_missing(self):
        with self.assertRaises(RuntimeError):
            RedisMetricsRepository(
                connection_settings=RedisConnectionSettings(
                    redis_url="redis://localhost:6379/0",
                ),
                redis_client=None,
                now=lambda: datetime(2026, 4, 20, 12, 0, 0),
                max_route_latency_samples=4,
            )

    @patch("monitoring.infrastructure.repositories.redis")
    def test_repository_init_raises_when_redis_server_is_unreachable(
        self,
        redis_module,
    ):
        redis_client = Mock()
        redis_client.ping.side_effect = RuntimeError("connection refused")
        redis_module.Redis.from_url.return_value = redis_client

        with self.assertRaises(RuntimeError):
            RedisMetricsRepository(
                now=lambda: datetime(2026, 4, 20, 12, 0, 0),
                max_route_latency_samples=4,
            )

        redis_module.Redis.from_url.assert_called_once_with(
            "redis://127.0.0.1:6379/0",
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )

    def test_parse_event_hash_field_returns_unknown_when_invalid(self):
        self.assertEqual(
            self.repo._parse_event_hash_field("broken"),
            ("unknown", "unknown"),
        )

    def test_resolve_latency_percentiles_from_samples_clamps_negative_sample(self):
        low, high = self.repo._resolve_latency_percentiles_from_samples([-10.0, 20.0, 30.0])

        self.assertEqual(low, 30.0)
        self.assertEqual(high, 30.0)

    def test_resolve_latency_percentiles_from_samples_with_empty_samples(self):
        low, high = self.repo._resolve_latency_percentiles_from_samples([])

        self.assertEqual(low, 0.0)
        self.assertEqual(high, 0.0)


class RedisMetricsRepositoryTest(SimpleTestCase):
    def setUp(self):
        self.redis_client = _FakeRedisClient()
        self.repo = RedisMetricsRepository(
            redis_client=self.redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_namespace_settings=RedisNamespaceSettings(
                key_prefix="monitoring_test",
                key_namespace_version="v2",
            ),
            key_ttl_seconds=3600,
            realtime_window_seconds=60,
            realtime_bucket_seconds=10,
            max_realtime_records=100,
            max_route_latency_samples=4,
        )

    def _event(
        self,
        *,
        route="/upload",
        method="POST",
        status_code=200,
        duration_ms=120.0,
        created_at=None,
    ):
        return RequestMetricEvent(
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            created_at=created_at or datetime(2026, 4, 20, 11, 59, 0),
        )

    def _auth_event(
        self,
        *,
        event_name="login",
        outcome="success",
        endpoint="/auth/login/",
    ):
        return AuthMetricEvent(
            event_name=event_name,
            outcome=outcome,
            endpoint=endpoint,
            created_at=datetime(2026, 4, 20, 11, 59, 0),
        )

    def test_record_request_and_event_generate_expected_snapshot(self):
        self.repo.record_request(self._event(status_code=200, duration_ms=100.0))
        self.repo.record_request(self._event(status_code=502, duration_ms=250.0))
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))
        self.repo.record_event(self._auth_event(event_name="login", outcome="success"))

        snapshot = self.repo.get_snapshot()
        self.assertEqual(snapshot.total_requests, 2)
        self.assertEqual(snapshot.total_errors, 1)
        self.assertEqual(snapshot.routes[0].route, "/upload")
        self.assertEqual(snapshot.routes[0].method, "POST")
        self.assertEqual(snapshot.routes[0].avg_latency_ms, 175.0)
        self.assertEqual(snapshot.routes[0].max_latency_ms, 250.0)
        self.assertEqual(snapshot.routes[0].p95_latency_ms, 250.0)
        self.assertEqual(snapshot.routes[0].p99_latency_ms, 250.0)
        self.assertEqual(snapshot.to_dict()["events"]["login"]["success"], 2)
        self.assertEqual(
            sum(point.requests for point in snapshot.timeseries),
            2,
        )
        self.assertTrue(any(key.startswith("monitoring_test:v2:") for key in self.redis_client._expirations))

    def test_normalization_and_reset(self):
        self.repo.record_request(self._event(route=" ", method=" ", duration_ms=-1.0))
        self.repo.record_event(self._auth_event(event_name=" ", outcome=" "))

        before_reset = self.repo.get_snapshot()
        self.assertEqual(before_reset.routes[0].route, "unknown")
        self.assertEqual(before_reset.routes[0].method, "UNKNOWN")
        self.assertEqual(before_reset.to_dict()["events"]["unknown"]["unknown"], 1)

        self.repo.reset()
        after_reset = self.repo.get_snapshot()
        self.assertEqual(after_reset.total_requests, 0)
        self.assertEqual(after_reset.routes, ())
        self.assertEqual(after_reset.events, ())


class RedisMetricsRepositorySnapshotCacheTest(SimpleTestCase):
    def test_get_snapshot_uses_cache_within_ttl_window(self):
        now = datetime(2026, 4, 20, 12, 0, 0)
        repository = RedisMetricsRepository(
            redis_client=Mock(),
            now=lambda: now,
            max_route_latency_samples=4,
            snapshot_cache_ttl_seconds=10.0,
        )

        pipeline = Mock()
        pipeline.execute.return_value = [set(), {}, None, []]
        repository._redis.pipeline.return_value = pipeline

        repository.get_snapshot()
        repository.get_snapshot()

        self.assertEqual(repository._redis.pipeline.call_count, 1)

    def test_get_snapshot_refreshes_after_ttl_window(self):
        now_values = [
            datetime(2026, 4, 20, 12, 0, 0),
            datetime(2026, 4, 20, 12, 0, 11),
        ]

        def now() -> datetime:
            return now_values.pop(0)

        repository = RedisMetricsRepository(
            redis_client=Mock(),
            now=now,
            max_route_latency_samples=4,
            snapshot_cache_ttl_seconds=5.0,
        )

        pipeline = Mock()
        pipeline.execute.return_value = [set(), {}, None, []]
        repository._redis.pipeline.return_value = pipeline

        repository.get_snapshot()
        repository.get_snapshot()

        self.assertEqual(repository._redis.pipeline.call_count, 2)

    def test_record_request_invalidates_snapshot_cache(self):
        now = datetime(2026, 4, 20, 12, 0, 0)
        repository = RedisMetricsRepository(
            redis_client=_FakeRedisClient(),
            now=lambda: now,
            max_route_latency_samples=4,
            snapshot_cache_ttl_seconds=120.0,
        )

        baseline_snapshot = repository.get_snapshot()
        self.assertEqual(baseline_snapshot.total_requests, 0)

        repository.record_request(
            RequestMetricEvent(
                route="/upload",
                method="POST",
                status_code=200,
                duration_ms=100.0,
                created_at=now,
            )
        )

        updated_snapshot = repository.get_snapshot()
        self.assertEqual(updated_snapshot.total_requests, 1)

    def test_get_snapshot_disables_cache_when_ttl_is_zero(self):
        now = datetime(2026, 4, 20, 12, 0, 0)
        repository = RedisMetricsRepository(
            redis_client=Mock(),
            now=lambda: now,
            max_route_latency_samples=4,
            snapshot_cache_ttl_seconds=0,
        )

        pipeline = Mock()
        pipeline.execute.return_value = [set(), {}, None, []]
        repository._redis.pipeline.return_value = pipeline

        repository.get_snapshot()
        repository.get_snapshot()

        self.assertEqual(repository._redis.pipeline.call_count, 2)
        self.assertIsNone(repository._snapshot_cache)
        self.assertIsNone(repository._snapshot_cache_expires_at_ms)

class ResilientMetricsRepositoryTest(SimpleTestCase):
    def test_falls_back_when_primary_record_request_fails(self):
        primary = Mock()
        fallback = Mock()
        primary.record_request.side_effect = RuntimeError("redis down")

        repository = ResilientMetricsRepository(
            primary_repository=primary,
            fallback_repository=fallback,
        )
        event = RequestMetricEvent(
            route="/upload",
            method="POST",
            status_code=200,
            duration_ms=10.0,
            created_at=datetime(2026, 4, 20, 10, 0, 0),
        )

        repository.record_request(event)
        repository.record_event(
            AuthMetricEvent(
                event_name="login",
                outcome="success",
                endpoint="/auth/login/",
                created_at=datetime(2026, 4, 20, 10, 0, 0),
            )
        )

        self.assertTrue(repository.degraded_to_fallback)
        primary.record_request.assert_called_once_with(event)
        fallback.record_request.assert_called_once_with(event)
        fallback.record_event.assert_called_once()
        primary.record_event.assert_not_called()

    def test_get_snapshot_uses_fallback_when_primary_fails(self):
        primary = Mock()
        fallback = Mock()
        snapshot = Mock()
        primary.get_snapshot.side_effect = RuntimeError("redis down")
        fallback.get_snapshot.return_value = snapshot

        repository = ResilientMetricsRepository(
            primary_repository=primary,
            fallback_repository=fallback,
        )

        result = repository.get_snapshot()

        self.assertIs(result, snapshot)
        self.assertTrue(repository.degraded_to_fallback)
        primary.get_snapshot.assert_called_once_with()
        fallback.get_snapshot.assert_called_once_with()

    def test_reset_calls_primary_and_fallback_reset(self):
        primary = Mock()
        fallback = Mock()
        repository = ResilientMetricsRepository(
            primary_repository=primary,
            fallback_repository=fallback,
        )

        repository.reset()

        primary.reset.assert_called_once_with()
        fallback.reset.assert_called_once_with()

    def test_reset_handles_reset_exceptions(self):
        primary = Mock()
        fallback = Mock()
        primary.reset.side_effect = RuntimeError("primary down")
        fallback.reset.side_effect = RuntimeError("fallback down")

        repository = ResilientMetricsRepository(
            primary_repository=primary,
            fallback_repository=fallback,
        )

        repository.reset()
