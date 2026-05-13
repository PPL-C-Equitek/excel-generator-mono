import type {
    MonitoringReadyPayload,
    MonitoringStatsPayload,
    MonitoringTimeseriesPoint,
} from '@/services/monitoring'
import { clamp, formatTimeLabel } from './monitoringUi'
import {
    monitoringRouteVisibilityPolicy,
    type MonitoringRouteVisibilityPolicy,
} from './monitoringRoutePolicy'
import type {
    AuthEventSummaryRow,
    ErrorRateMeter,
    EventRow,
    LatencyChartModel,
    LatencySeriesPoint,
    ReadinessMeter,
    RealtimeTotals,
    RouteSummaryRow,
} from './monitoringViewModelTypes'

const MAX_REALTIME_LATENCY_TICKS = 6
const MAX_ROUTE_SUMMARY_ROWS = 6
const MAX_AUTH_EVENT_SUMMARY_ROWS = 8
const MAX_ROUTE_LATENCY_ROWS = 8
const LATENCY_CHART_WIDTH = 520
const LATENCY_CHART_HEIGHT = 220
const LATENCY_CHART_PADDING_X = 26
const LATENCY_CHART_TOP_PADDING = 16
const LATENCY_CHART_BOTTOM_PADDING = 30

type TimeseriesPointCandidate = MonitoringTimeseriesPoint | null | undefined

type RouteProjection = Readonly<{
    visibleRoutes: MonitoringStatsPayload['routes']
    routeSummaryRows: RouteSummaryRow[]
    maxRouteRequests: number
}>

type EventProjection = Readonly<{
    eventRows: EventRow[]
    authEventSummaryRows: AuthEventSummaryRow[]
    maxEventCount: number
}>

export type MonitoringDashboardProjection = Readonly<{
    hasRealtimeSeries: boolean
    realtimeWindowSeconds: number
    realtimeBucketSeconds: number
    realtimeTotals: RealtimeTotals
    eventRows: EventRow[]
    authEventSummaryRows: AuthEventSummaryRow[]
    maxEventCount: number
    visibleRoutes: MonitoringStatsPayload['routes']
    routeSummaryRows: RouteSummaryRow[]
    maxRouteRequests: number
    latencySeries: LatencySeriesPoint[]
    latencyChart: LatencyChartModel
    errorRateMeter: ErrorRateMeter
    readinessMeter: ReadinessMeter
}>

type MonitoringDashboardProjectionInput = Readonly<{
    statsPayload: MonitoringStatsPayload | null
    readyPayload: MonitoringReadyPayload | null
    routeVisibilityPolicy?: MonitoringRouteVisibilityPolicy
}>

function calculateBarWidth(value: number, maxValue: number): string {
    return `${Math.max(8, Math.round((value / maxValue) * 100))}%`
}

function shouldShowLatencyPointLabel(
    seriesLength: number,
    index: number,
    isLastEntry: boolean,
): boolean {
    if (seriesLength <= 6) {
        return true
    }
    if (isLastEntry) {
        return true
    }
    return index % 2 === 0
}

function collectLatestTimeseriesPoints(
    points: readonly TimeseriesPointCandidate[],
): MonitoringTimeseriesPoint[] {
    const latestPoints: MonitoringTimeseriesPoint[] = []

    for (let index = points.length - 1; index >= 0 && latestPoints.length < MAX_REALTIME_LATENCY_TICKS; index -= 1) {
        const point = points[index]
        if (point !== null && point !== undefined) {
            latestPoints.push(point)
        }
    }

    latestPoints.reverse()
    return latestPoints
}

function buildRouteProjection(
    statsPayload: MonitoringStatsPayload | null,
    routeVisibilityPolicy: MonitoringRouteVisibilityPolicy,
): RouteProjection {
    if (!statsPayload) {
        return {
            visibleRoutes: [],
            routeSummaryRows: [],
            maxRouteRequests: 1,
        }
    }

    const visibleRoutes: MonitoringStatsPayload['routes'] = []
    let maxRouteRequests = 1

    for (const routeRow of statsPayload.routes) {
        if (!routeVisibilityPolicy.shouldShowRoute(routeRow.route)) {
            continue
        }

        visibleRoutes.push(routeRow)
        maxRouteRequests = Math.max(maxRouteRequests, routeRow.total_requests)
    }

    return {
        visibleRoutes,
        routeSummaryRows: visibleRoutes
            .slice(0, MAX_ROUTE_SUMMARY_ROWS)
            .map((routeRow) => ({
                route: routeRow.route,
                method: routeRow.method,
                totalRequests: routeRow.total_requests,
                totalErrors: routeRow.total_errors,
                avgLatencyMs: routeRow.avg_latency_ms,
                requestWidth: calculateBarWidth(routeRow.total_requests, maxRouteRequests),
            })),
        maxRouteRequests,
    }
}

function buildEventProjection(statsPayload: MonitoringStatsPayload | null): EventProjection {
    if (!statsPayload) {
        return {
            eventRows: [],
            authEventSummaryRows: [],
            maxEventCount: 1,
        }
    }

    const eventRows: EventRow[] = []
    let maxEventCount = 1

    for (const [eventName, outcomes] of Object.entries(statsPayload.events)) {
        for (const [outcome, count] of Object.entries(outcomes)) {
            eventRows.push({
                eventName,
                outcome,
                count,
            })
            maxEventCount = Math.max(maxEventCount, count)
        }
    }

    eventRows.sort((a, b) => b.count - a.count || a.eventName.localeCompare(b.eventName))

    return {
        eventRows,
        authEventSummaryRows: eventRows
            .slice(0, MAX_AUTH_EVENT_SUMMARY_ROWS)
            .map((eventRow) => ({
                ...eventRow,
                eventWidth: calculateBarWidth(eventRow.count, maxEventCount),
            })),
        maxEventCount,
    }
}

function resolveRealtimeWindowSeconds({
    hasRealtimeSeries,
    rawRealtimeWindowSeconds,
    realtimeBucketSeconds,
    renderedBucketCount,
}: Readonly<{
    hasRealtimeSeries: boolean
    rawRealtimeWindowSeconds: number
    realtimeBucketSeconds: number
    renderedBucketCount: number
}>): number {
    if (!hasRealtimeSeries || realtimeBucketSeconds <= 0) {
        return rawRealtimeWindowSeconds
    }

    const renderedWindowSeconds = realtimeBucketSeconds * renderedBucketCount
    if (rawRealtimeWindowSeconds <= 0) {
        return renderedWindowSeconds
    }

    return Math.min(rawRealtimeWindowSeconds, renderedWindowSeconds)
}

function buildRealtimeTotals(timeseriesPoints: readonly MonitoringTimeseriesPoint[]): RealtimeTotals {
    if (timeseriesPoints.length === 0) {
        return null
    }

    let requests = 0
    let errors = 0
    for (const point of timeseriesPoints) {
        requests += point.requests
        errors += point.errors
    }

    return {
        requests,
        errors,
        errorRate: requests > 0 ? errors / requests : 0,
    }
}

function buildRealtimeLatencySeries(
    timeseriesPoints: readonly MonitoringTimeseriesPoint[],
): LatencySeriesPoint[] {
    return timeseriesPoints.map((point, index) => ({
        id: index + 1,
        label: formatTimeLabel(point.timestamp),
        value: point.avg_latency_ms,
        requests: point.requests,
    }))
}

function buildRouteLatencySeries(
    visibleRoutes: MonitoringStatsPayload['routes'],
): LatencySeriesPoint[] {
    return visibleRoutes
        .slice(0, MAX_ROUTE_LATENCY_ROWS)
        .map((routeRow, index) => ({
            id: index + 1,
            label: routeRow.route,
            value: routeRow.avg_latency_ms,
            requests: routeRow.total_requests,
        }))
}

function buildLatencyChart(
    latencySeries: readonly LatencySeriesPoint[],
    hasRealtimeSeries: boolean,
): LatencyChartModel {
    if (latencySeries.length === 0) {
        return {
            linePoints: '',
            areaPath: '',
            maxLatency: 0,
            maxRequests: 0,
            points: [],
        }
    }

    const plotWidth = LATENCY_CHART_WIDTH - LATENCY_CHART_PADDING_X * 2
    const plotHeight = LATENCY_CHART_HEIGHT - LATENCY_CHART_TOP_PADDING - LATENCY_CHART_BOTTOM_PADDING
    let maxLatency = 1
    let maxRequests = 0

    for (const entry of latencySeries) {
        maxLatency = Math.max(maxLatency, entry.value)
        maxRequests = Math.max(maxRequests, entry.requests)
    }

    const points = latencySeries.map((entry, index) => {
        const normalizedX = latencySeries.length === 1 ? 0.5 : index / (latencySeries.length - 1)
        const normalizedY = clamp(entry.value / maxLatency, 0, 1)
        const x = LATENCY_CHART_PADDING_X + normalizedX * plotWidth
        const y = LATENCY_CHART_TOP_PADDING + (1 - normalizedY) * plotHeight
        const isLastEntry = index === latencySeries.length - 1

        return {
            id: entry.id,
            x,
            y,
            xLabel: hasRealtimeSeries ? entry.label : String(entry.id),
            showLabel: shouldShowLatencyPointLabel(latencySeries.length, index, isLastEntry),
        }
    })

    const linePoints = points.map((point) => `${point.x},${point.y}`).join(' ')
    const firstPoint = points.at(0)!
    const lastPoint = points.at(-1)!
    const polylinePoints = points.map((point) => `${point.x} ${point.y}`).join(' L ')
    const baselineY = LATENCY_CHART_HEIGHT - LATENCY_CHART_BOTTOM_PADDING
    const areaPath = `M ${firstPoint.x} ${baselineY} L ${polylinePoints} L ${lastPoint.x} ${baselineY} Z`

    return {
        linePoints,
        areaPath,
        maxLatency,
        maxRequests,
        points,
    }
}

function buildErrorRateMeter(sourceErrorRate: number): ErrorRateMeter {
    const errorRate = clamp(sourceErrorRate, 0, 1)
    const meterPercent = errorRate * 100

    return {
        percentText: `${meterPercent.toFixed(2)}%`,
        progressLength: 251.2 * errorRate,
        colorClass: errorRate <= 0.05 ? 'text-blue-600' : 'text-red-700',
    }
}

function buildReadinessMeter(readyPayload: MonitoringReadyPayload | null): ReadinessMeter {
    if (!readyPayload || readyPayload.checks.length === 0) {
        return {
            percentText: '--',
            progressLength: 0,
            colorClass: 'text-gray-600',
            healthyChecks: 0,
            totalChecks: 0,
        }
    }

    let healthyChecks = 0
    for (const check of readyPayload.checks) {
        if (check.status.toLowerCase() === 'ok') {
            healthyChecks += 1
        }
    }

    const totalChecks = readyPayload.checks.length
    const readinessRate = clamp(healthyChecks / totalChecks, 0, 1)

    return {
        percentText: `${(readinessRate * 100).toFixed(0)}%`,
        progressLength: 251.2 * readinessRate,
        colorClass: readinessRate >= 0.8 ? 'text-blue-600' : 'text-red-700',
        healthyChecks,
        totalChecks,
    }
}

export function createMonitoringDashboardProjection({
    statsPayload,
    readyPayload,
    routeVisibilityPolicy = monitoringRouteVisibilityPolicy,
}: MonitoringDashboardProjectionInput): MonitoringDashboardProjection {
    const routeProjection = buildRouteProjection(statsPayload, routeVisibilityPolicy)
    const eventProjection = buildEventProjection(statsPayload)
    const timeseriesPoints = collectLatestTimeseriesPoints(statsPayload?.timeseries?.points ?? [])
    const realtimeBucketSeconds = statsPayload?.timeseries?.bucket_seconds ?? 0
    const hasRealtimeSeries = timeseriesPoints.length > 0
    const realtimeWindowSeconds = resolveRealtimeWindowSeconds({
        hasRealtimeSeries,
        rawRealtimeWindowSeconds: statsPayload?.timeseries?.window_seconds ?? 0,
        realtimeBucketSeconds,
        renderedBucketCount: timeseriesPoints.length,
    })
    const realtimeTotals = buildRealtimeTotals(timeseriesPoints)
    const latencySeries = hasRealtimeSeries
        ? buildRealtimeLatencySeries(timeseriesPoints)
        : buildRouteLatencySeries(routeProjection.visibleRoutes)
    const latencyChart = buildLatencyChart(latencySeries, hasRealtimeSeries)
    const errorRateMeter = buildErrorRateMeter(realtimeTotals?.errorRate ?? statsPayload?.totals.error_rate ?? 0)

    return {
        hasRealtimeSeries,
        realtimeWindowSeconds,
        realtimeBucketSeconds,
        realtimeTotals,
        ...eventProjection,
        ...routeProjection,
        latencySeries,
        latencyChart,
        errorRateMeter,
        readinessMeter: buildReadinessMeter(readyPayload),
    }
}
