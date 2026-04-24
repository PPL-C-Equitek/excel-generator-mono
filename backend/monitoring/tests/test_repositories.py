from datetime import datetime
from unittest.mock import Mock

from django.test import SimpleTestCase

from monitoring.entities import AuthMetricEvent, RequestMetricEvent
from monitoring.repositories import (
    InMemoryMetricsRepository,
    RedisMetricsRepository,
    ResilientMetricsRepository,
    _RouteAccumulator,
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

    def zremrangebyscore(self, *args, **kwargs):
        return self._queue("zremrangebyscore", *args, **kwargs)

    def smembers(self, *args, **kwargs):
        return self._queue("smembers", *args, **kwargs)

    def hgetall(self, *args, **kwargs):
        return self._queue("hgetall", *args, **kwargs)

    def zrangebyscore(self, *args, **kwargs):
        return self._queue("zrangebyscore", *args, **kwargs)

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


class RedisMetricsRepositoryTest(SimpleTestCase):
    def setUp(self):
        self.redis_client = _FakeRedisClient()
        self.repo = RedisMetricsRepository(
            redis_client=self.redis_client,
            now=lambda: datetime(2026, 4, 20, 12, 0, 0),
            key_prefix="monitoring_test",
            key_namespace_version="v2",
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
