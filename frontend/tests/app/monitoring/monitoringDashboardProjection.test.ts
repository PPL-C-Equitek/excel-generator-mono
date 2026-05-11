import { describe, expect, it } from 'vitest'
import type { MonitoringReadyPayload, MonitoringStatsPayload } from '../../../src/services/monitoring'
import { createMonitoringRouteVisibilityPolicy } from '../../../src/app/monitoring/monitoringRoutePolicy'
import { createMonitoringDashboardProjection } from '../../../src/app/monitoring/monitoringDashboardProjection'

function makeRoute(index: number, overrides: Partial<MonitoringStatsPayload['routes'][number]> = {}): MonitoringStatsPayload['routes'][number] {
    return {
        route: `/route-${index}/`,
        method: 'GET',
        total_requests: 100 - index * 10,
        total_errors: index,
        error_rate: 0,
        avg_latency_ms: 20 + index,
        max_latency_ms: 40 + index,
        ...overrides,
    }
}

function makeReadyPayload(checks: MonitoringReadyPayload['checks']): MonitoringReadyPayload {
    return {
        status: 'degraded',
        timestamp: '2026-04-24T10:00:01Z',
        checks,
    }
}

describe('monitoring dashboard projection', () => {
    it('collects only the latest valid realtime buckets and builds chart data in one projection', () => {
        const statsPayload: MonitoringStatsPayload = {
            status: 'ok',
            generated_at: '2026-04-24T10:00:02Z',
            totals: { requests: 999, errors: 99, error_rate: 0.99 },
            routes: [],
            events: {},
            timeseries: {
                window_seconds: 300,
                bucket_seconds: 10,
                points: [
                    null,
                    { timestamp: '2026-04-24T10:00:00Z', requests: 1, errors: 0, error_rate: 0, avg_latency_ms: 10 },
                    undefined,
                    { timestamp: '2026-04-24T10:00:10Z', requests: 2, errors: 1, error_rate: 0.5, avg_latency_ms: 20 },
                    { timestamp: '2026-04-24T10:00:20Z', requests: 3, errors: 0, error_rate: 0, avg_latency_ms: 30 },
                    { timestamp: '2026-04-24T10:00:30Z', requests: 4, errors: 1, error_rate: 0.25, avg_latency_ms: 40 },
                    { timestamp: '2026-04-24T10:00:40Z', requests: 5, errors: 0, error_rate: 0, avg_latency_ms: 50 },
                    { timestamp: '2026-04-24T10:00:50Z', requests: 6, errors: 1, error_rate: 0.166, avg_latency_ms: 60 },
                    { timestamp: '2026-04-24T10:01:00Z', requests: 7, errors: 0, error_rate: 0, avg_latency_ms: 70 },
                ],
            } as unknown as MonitoringStatsPayload['timeseries'],
        }

        const projection = createMonitoringDashboardProjection({
            statsPayload,
            readyPayload: null,
        })

        expect(projection.hasRealtimeSeries).toBe(true)
        expect(projection.latencySeries.map((point) => point.value)).toEqual([20, 30, 40, 50, 60, 70])
        expect(projection.realtimeTotals).toEqual({
            requests: 27,
            errors: 3,
            errorRate: 3 / 27,
        })
        expect(projection.realtimeWindowSeconds).toBe(60)
        expect(projection.latencyChart.maxLatency).toBe(70)
        expect(projection.latencyChart.maxRequests).toBe(7)
        expect(projection.latencyChart.points).toHaveLength(6)
        expect(projection.errorRateMeter.percentText).toBe('11.11%')
    })

    it('projects route, auth event, and readiness summaries with injected visibility policy', () => {
        const statsPayload: MonitoringStatsPayload = {
            status: 'ok',
            generated_at: '2026-04-24T10:00:02Z',
            totals: { requests: 100, errors: 4, error_rate: 0.04 },
            routes: [
                makeRoute(0, { route: '/internal/metrics/', total_requests: 999 }),
                ...Array.from({ length: 8 }, (_, index) => makeRoute(index + 1)),
            ],
            events: Object.fromEntries(
                Array.from({ length: 10 }, (_, index) => [
                    `event_${index + 1}`,
                    { success: 10 - index },
                ])
            ),
        }
        const readyPayload = makeReadyPayload([
            { name: 'database', status: 'ok', latency_ms: 3, is_critical: true },
            { name: 'storage', status: 'ok', latency_ms: 4, is_critical: true },
            { name: 'openai_config', status: 'error', latency_ms: 8, is_critical: true },
            { name: 'queue', status: 'ok', latency_ms: 5, is_critical: false },
        ])

        const projection = createMonitoringDashboardProjection({
            statsPayload,
            readyPayload,
            routeVisibilityPolicy: createMonitoringRouteVisibilityPolicy(['internal']),
        })

        expect(projection.visibleRoutes.map((route) => route.route)).not.toContain('/internal/metrics/')
        expect(projection.maxRouteRequests).toBe(90)
        expect(projection.routeSummaryRows).toHaveLength(6)
        expect(projection.routeSummaryRows[0]).toMatchObject({
            route: '/route-1/',
            requestWidth: '100%',
        })
        expect(projection.routeSummaryRows.at(-1)).toMatchObject({
            route: '/route-6/',
            requestWidth: '44%',
        })
        expect(projection.latencySeries).toHaveLength(8)
        expect(projection.authEventSummaryRows).toHaveLength(8)
        expect(projection.authEventSummaryRows.at(-1)).toMatchObject({
            eventName: 'event_8',
            eventWidth: '30%',
        })
        expect(projection.errorRateMeter).toMatchObject({
            percentText: '4.00%',
            colorClass: 'text-blue-600',
        })
        expect(projection.readinessMeter).toMatchObject({
            percentText: '75%',
            colorClass: 'text-red-700',
            healthyChecks: 3,
            totalChecks: 4,
        })
    })

    it('returns safe empty projection defaults before monitoring stats arrive', () => {
        const projection = createMonitoringDashboardProjection({
            statsPayload: null,
            readyPayload: null,
        })

        expect(projection.visibleRoutes).toEqual([])
        expect(projection.routeSummaryRows).toEqual([])
        expect(projection.eventRows).toEqual([])
        expect(projection.authEventSummaryRows).toEqual([])
        expect(projection.latencyChart).toEqual({
            linePoints: '',
            areaPath: '',
            maxLatency: 0,
            maxRequests: 0,
            points: [],
        })
        expect(projection.readinessMeter.percentText).toBe('--')
    })
})
