import type {
    MonitoringAccessDecision,
    MonitoringCheck,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringRouteStat,
    MonitoringStatsPayload,
    MonitoringTimeseriesPoint,
} from './monitoring.types'

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toStringValue(value: unknown, fallback = ''): string {
    return typeof value === 'string' ? value : fallback
}

function toNumberValue(value: unknown, fallback = 0): number {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value
    }
    return fallback
}

function toBooleanValue(value: unknown, fallback = false): boolean {
    return typeof value === 'boolean' ? value : fallback
}

function mapMonitoringCheck(value: unknown): MonitoringCheck {
    const record = isRecord(value) ? value : {}
    const message = toStringValue(record.message)

    return {
        name: toStringValue(record.name, 'unknown'),
        status: toStringValue(record.status, 'unknown'),
        latency_ms: toNumberValue(record.latency_ms, 0),
        is_critical: toBooleanValue(record.is_critical, true),
        ...(message ? { message } : {}),
    }
}

function mapMonitoringRoute(value: unknown): MonitoringRouteStat {
    const record = isRecord(value) ? value : {}

    return {
        route: toStringValue(record.route, 'unknown'),
        method: toStringValue(record.method, 'UNKNOWN'),
        total_requests: toNumberValue(record.total_requests, 0),
        total_errors: toNumberValue(record.total_errors, 0),
        error_rate: toNumberValue(record.error_rate, 0),
        avg_latency_ms: toNumberValue(record.avg_latency_ms, 0),
        max_latency_ms: toNumberValue(record.max_latency_ms, 0),
    }
}

function mapMonitoringTimeseriesPoint(value: unknown): MonitoringTimeseriesPoint {
    const record = isRecord(value) ? value : {}

    return {
        timestamp: toStringValue(record.timestamp, ''),
        requests: toNumberValue(record.requests, 0),
        errors: toNumberValue(record.errors, 0),
        error_rate: toNumberValue(record.error_rate, 0),
        avg_latency_ms: toNumberValue(record.avg_latency_ms, 0),
    }
}

function mapEvents(value: unknown): Record<string, Record<string, number>> {
    if (!isRecord(value)) {
        return {}
    }

    const mapped: Record<string, Record<string, number>> = {}
    for (const [eventName, outcomesValue] of Object.entries(value)) {
        if (!isRecord(outcomesValue)) {
            continue
        }
        const outcomes: Record<string, number> = {}
        for (const [outcomeName, countValue] of Object.entries(outcomesValue)) {
            outcomes[outcomeName] = toNumberValue(countValue, 0)
        }
        mapped[eventName] = outcomes
    }
    return mapped
}

export function mapMonitoringLiveResponse(payload: unknown): MonitoringLivePayload {
    const record = isRecord(payload) ? payload : {}
    return {
        status: toStringValue(record.status, 'unknown'),
        timestamp: toStringValue(record.timestamp, ''),
    }
}

export function mapMonitoringAccessResponse(payload: unknown): MonitoringAccessDecision {
    const record = isRecord(payload) ? payload : {}
    return {
        allowed: toBooleanValue(record.allowed, false),
        reason: toStringValue(record.reason, 'unauthenticated'),
    }
}

export function mapMonitoringReadyResponse(payload: unknown): MonitoringReadyPayload {
    const record = isRecord(payload) ? payload : {}
    const checks = Array.isArray(record.checks) ? record.checks.map(mapMonitoringCheck) : []

    return {
        status: toStringValue(record.status, 'unknown'),
        timestamp: toStringValue(record.timestamp, ''),
        checks,
    }
}

export function mapMonitoringStatsResponse(payload: unknown): MonitoringStatsPayload {
    const record = isRecord(payload) ? payload : {}
    const totalsRecord = isRecord(record.totals) ? record.totals : {}
    const routes = Array.isArray(record.routes) ? record.routes.map(mapMonitoringRoute) : []
    const timeseriesRecord = isRecord(record.timeseries) ? record.timeseries : null

    return {
        status: toStringValue(record.status, 'unknown'),
        generated_at: toStringValue(record.generated_at, ''),
        totals: {
            requests: toNumberValue(totalsRecord.requests, 0),
            errors: toNumberValue(totalsRecord.errors, 0),
            error_rate: toNumberValue(totalsRecord.error_rate, 0),
        },
        routes,
        events: mapEvents(record.events),
        timeseries: timeseriesRecord
            ? {
                window_seconds: toNumberValue(timeseriesRecord.window_seconds, 0),
                bucket_seconds: toNumberValue(timeseriesRecord.bucket_seconds, 0),
                points: Array.isArray(timeseriesRecord.points)
                    ? timeseriesRecord.points.map(mapMonitoringTimeseriesPoint)
                    : [],
            }
            : undefined,
    }
}

