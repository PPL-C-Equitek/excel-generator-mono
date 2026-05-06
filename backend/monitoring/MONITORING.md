# Monitoring Module Documentation

Last updated: April 26, 2026

## 1. Scope

Monitoring module provides backend health/readiness checks, traffic metrics, auth activity metrics, snapshot API, and SSE stream for live dashboard updates.

This module is split into:
- `application`: access policy + orchestration services.
- `domain`: entities/contracts.
- `infrastructure`: repositories, health checks, Discord notifier.
- `interfaces/http`: endpoints, permissions/decorators, request metrics middleware.

---

## 2. High-Level Flow

1. Every incoming backend request is observed by `MonitoringRequestMetricsMiddleware`.
2. Request metrics are recorded (`route`, `method`, `status_code`, `duration_ms`) except for routes under `monitoring/*`.
3. Auth endpoints decorated with `@track_auth_metric(...)` emit auth event metrics.
4. `MonitoringService` serves:
- `live`: liveness payload.
- `readiness`: checks + HTTP status mapping.
- `stats`: aggregated metrics snapshot (with cache).
- `stats_json`: pre-serialized JSON for SSE efficiency.
5. Repository backend is `memory` or `redis` (with resilient fallback to memory if Redis fails).

---

## 3. Access Model

Monitoring access is evaluated by `MonitoringAccessPolicy`:
- `unauthenticated`: no authenticated user.
- `unverified`: authenticated user but `user.status != "verified"`.
- `no_account`: verified user without `MonitoringAccount`.
- `inactive`: monitoring account exists but inactive.
- `ok`: access granted.

`MonitoringAccount.has_access` is true only if:
- account is active, and
- user status is `verified`.

---

## 4. HTTP Endpoints

All routes are defined in `backend/monitoring/interfaces/http/urls.py`.

| Endpoint | Method | Auth | Behavior |
|---|---|---|---|
| `/monitoring/live/` | GET | Public | Liveness status + timestamp |
| `/monitoring/ready/` | GET | Monitoring account required | Readiness checks, returns `200` (`ok`) or `503` (`degraded/down`) |
| `/monitoring/stats/` | GET | Monitoring account required | Full metrics snapshot |
| `/monitoring/snapshot/` | GET | JWT optional | Always `200`; unauthorized gets `{access, ready:null, stats:null}` |
| `/monitoring/stream/` | GET | Monitoring account required | SSE stream (`text/event-stream`) |
| `/monitoring/access/` | GET | JWT required | Returns access decision (`allowed`, `reason`) |

### Stream query params
- `interval_seconds`: positive float; invalid/non-positive uses fallback `MONITORING_STREAM_INTERVAL_SECONDS`.
- `max_events`: positive int; invalid/non-positive ignored (infinite stream).

### Frontend integration summary
- Monitoring UI route: `/monitoring` (frontend app).
- Bootstrap strategy: initial load can use authenticated snapshot (`/monitoring/snapshot/`) when available.
- Live update strategy: after bootstrap, frontend prefers SSE (`/monitoring/stream/`).
- Polling fallback: periodic refresh runs only when no active SSE stream.
- Visibility optimization: stream/polling is paused when tab is hidden and resumed when visible again.

---

## 5. Metrics Semantics

### 5.1 Route metrics
- Error is counted when `status_code >= 400` (includes 4xx and 5xx).
- Route stats include totals, error rate, avg/max latency, p95, p99.
- Monitoring routes are excluded from request-metric recording by middleware.

### 5.2 Auth events
Auth outcomes are resolved from HTTP status:
- `< 400` -> `success`
- `400-499` -> `client_error`
- `>= 500` -> `server_error`
- exception in view -> `exception`

### 5.3 Realtime series
- Built from request records in fixed buckets.
- Defaults: window `300s`, bucket `10s`.
- Frontend uses the recent points for latency/traffic charting.

---

## 6. Repository Backends

### 6.1 Memory backend
- Fast local default.
- Data resets on process restart.

### 6.2 Redis backend
- Persisted in Redis with key prefix/namespace and optional TTL.
- Supports route ranking limit and snapshot cache TTL.
- If Redis init/runtime fails in resilient mode, repository degrades to in-memory fallback.

---

## 7. Readiness Checks

Default checks:
- `database` (critical)
- `storage` (critical)
- `openai_config` (non-critical)

When metrics backend is Redis:
- `redis` is also checked (non-critical by default).

Readiness status resolution:
- any critical failure -> `down` (`503`)
- only non-critical failure(s) -> `degraded` (`503`)
- all pass -> `ok` (`200`)

---

## 8. Discord Webhook Alerts

Readiness non-OK notifications are sent via `DiscordWebhookNotifier` when configured.

Trigger rules:
- only for non-`ok` readiness.
- cooldown applied by `MONITORING_READINESS_ALERT_COOLDOWN_SECONDS`.
- same status within cooldown is suppressed.

Required config:
- `MONITORING_DISCORD_WEBHOOK_URL`
- optional `MONITORING_DISCORD_WEBHOOK_USERNAME` (default `MonitoringBot`)
- optional `MONITORING_DISCORD_WEBHOOK_TIMEOUT_SECONDS` (default `3.0`)

Implementation detail:
- notifier sends JSON with `Content-Type: application/json` and explicit `User-Agent`.

---

## 9. Configuration

Defined in `backend/config/settings.py` and consumed in `monitoring/container.py` / views.

### Core
- `MONITORING_METRICS_BACKEND` (`memory` or `redis`, default `memory`)
- `MONITORING_STREAM_INTERVAL_SECONDS` (default `2.0`)
- `MONITORING_STATS_CACHE_TTL_SECONDS` (default `2.0`)
- `MONITORING_SNAPSHOT_READINESS_CACHE_TTL_SECONDS` (default `2.0`; used by `/monitoring/snapshot/` only)

### Realtime and route sampling
- `MONITORING_REALTIME_WINDOW_SECONDS` (default `300`)
- `MONITORING_REALTIME_BUCKET_SECONDS` (default `10`)
- `MONITORING_MAX_REALTIME_RECORDS` (default `10000`)
- `MONITORING_MAX_ROUTE_LATENCY_SAMPLES` (default `2048`)
- `MONITORING_MAX_ROUTES_PER_SNAPSHOT` (default `0`, means unlimited)

### Redis
- `MONITORING_REDIS_URL` (default `redis://127.0.0.1:6379/0`)
- `MONITORING_REDIS_KEY_PREFIX` (default `monitoring`)
- `MONITORING_REDIS_KEY_NAMESPACE_VERSION` (default `v1`)
- `MONITORING_REDIS_KEY_TTL_SECONDS` (default `86400`)
- `MONITORING_REDIS_SOCKET_TIMEOUT_SECONDS` (default `1.0`)
- `MONITORING_REDIS_CONNECT_TIMEOUT_SECONDS` (default `1.0`)
- `MONITORING_REDIS_SNAPSHOT_CACHE_TTL_SECONDS` (optional; if <=0 falls back to `MONITORING_STATS_CACHE_TTL_SECONDS`)

### Readiness alerting
- `MONITORING_DISCORD_WEBHOOK_URL` (default empty/disabled)
- `MONITORING_DISCORD_WEBHOOK_USERNAME` (default `MonitoringBot`)
- `MONITORING_DISCORD_WEBHOOK_TIMEOUT_SECONDS` (default `3.0`)
- `MONITORING_READINESS_ALERT_COOLDOWN_SECONDS` (default `300`)

### Endpoint rate limiting
- `MONITORING_RATE_LIMIT_MAX_REQUESTS` (default `120`)
- `MONITORING_RATE_LIMIT_PER` (`second(s)` or `minute(s)`, default `minute`)

---

## 10. Local Setup and Verification

Run from repo root (`excel-generator-mono`), backend on `localhost:8000`.

### 10.1 Create/activate monitoring account

```bash
cd backend
python manage.py shell -c "from authentication.models import User; from monitoring.models import MonitoringAccount; u=User.objects.get(email='monitoring@example.com'); u.status='verified'; u.save(update_fields=['status']); MonitoringAccount.objects.provision_for_user(user=u, is_active=True)"
```

### 10.2 Login and capture token

```bash
curl -s -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"monitoring@example.com","password":"your-password"}'
```

Use returned `access_token` as `TOKEN`.

### 10.3 Test endpoints

```bash
curl -s http://localhost:8000/monitoring/live/
curl -s -H "Authorization: Bearer TOKEN" http://localhost:8000/monitoring/access/
curl -s -H "Authorization: Bearer TOKEN" http://localhost:8000/monitoring/snapshot/
curl -N -H "Authorization: Bearer TOKEN" -H "Accept: text/event-stream" "http://localhost:8000/monitoring/stream/?interval_seconds=5&max_events=3"
```

### 10.4 Compare with normal user (no monitoring account)

```bash
curl -s -H "Authorization: Bearer NORMAL_USER_TOKEN" http://localhost:8000/monitoring/access/
curl -s -i -H "Authorization: Bearer NORMAL_USER_TOKEN" http://localhost:8000/monitoring/stats/
curl -s -H "Authorization: Bearer NORMAL_USER_TOKEN" http://localhost:8000/monitoring/snapshot/
```

Expected:
- `/monitoring/access/` -> `allowed: false`, reason typically `no_account` or `unverified`.
- `/monitoring/stats/` -> `403`.
- `/monitoring/snapshot/` -> `200` with `ready: null` and `stats: null`.

---

## 11. Troubleshooting

### `401` on protected endpoints
- Missing/invalid JWT.
- Check `Authorization: Bearer <token>`.

### `403` for authenticated user
- User is not verified, or no `MonitoringAccount`, or account inactive.
- Check `/monitoring/access/` reason.

### `404` for `/monitoring/stream/` from frontend
- Frontend may be calling its own dev server route.
- Verify `NEXT_PUBLIC_API_URL` points to backend API host.

### `406 Not Acceptable` when testing stream
- Send `Accept: text/event-stream`.

### No route metrics shown
- Monitoring routes are intentionally excluded.
- Generate normal API traffic first (non-`/monitoring/*` endpoints).

### Redis connection errors
- If backend is `redis`, ensure Redis is running and reachable.
- If Redis fails at startup in resilient path, service falls back to memory repository.

### Auth events mismatch with route row
- Route metrics aggregate HTTP status by route (`>=400` counts as error).
- Auth event outcome uses decorated auth endpoints and outcome mapping by response status/exception.
