import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
    MonitoringAccessDecision,
    MonitoringAuthenticatedSnapshot,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
    MonitoringStatsStreamHandle,
    MonitoringStatsStreamOptions,
} from '@/services/monitoring'
import { clamp, formatTimeLabel } from './monitoringUi'
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
import { getMonitoringAuthToken, MONITORING_STREAM_UNEXPECTED_CLOSE_MESSAGE } from '@/services/monitoring'
import { monitoringRouteVisibilityPolicy } from './monitoringRoutePolicy'

const DEFAULT_AUTO_REFRESH_INTERVAL_MS = 5000
const STALE_THRESHOLD_MULTIPLIER = 3
const MIN_STALE_THRESHOLD_MS = 15000
const RETRY_BASE_DELAY_MS = 2000
const RETRY_MAX_DELAY_MS = 30000
const RETRY_TICK_INTERVAL_MS = 1000
const MAX_REALTIME_LATENCY_TICKS = 6
const MAX_ROUTE_SUMMARY_ROWS = 6
const MAX_AUTH_EVENT_SUMMARY_ROWS = 8
const LATENCY_CHART_WIDTH = 520
const LATENCY_CHART_HEIGHT = 220
const LATENCY_CHART_PADDING_X = 26
const LATENCY_CHART_TOP_PADDING = 16
const LATENCY_CHART_BOTTOM_PADDING = 30

export type MonitoringDashboardService = {
    getMonitoringLive: () => Promise<MonitoringLivePayload>
    getMonitoringAccess: (accessToken?: string) => Promise<MonitoringAccessDecision>
    getMonitoringReady: (accessToken?: string) => Promise<MonitoringReadyPayload>
    getMonitoringStats: (accessToken?: string) => Promise<MonitoringStatsPayload>
    getMonitoringStatsStream?: (options: MonitoringStatsStreamOptions) => Promise<MonitoringStatsStreamHandle>
    getMonitoringAuthenticatedSnapshot?: () => Promise<MonitoringAuthenticatedSnapshot>
}

export type MonitoringDashboardViewModel = {
    livePayload: MonitoringLivePayload | null
    accessDecision: MonitoringAccessDecision | null
    readyPayload: MonitoringReadyPayload | null
    statsPayload: MonitoringStatsPayload | null
    isLoading: boolean
    isRefreshing: boolean
    errorMessage: string | null
    consecutiveFailures: number
    retryInSeconds: number
    nextRetryAtMs: number | null
    isDataStale: boolean
    lastSync: string
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
    refreshDashboard: () => void
}

type UseMonitoringDashboardModelParams = Readonly<{
    monitoringService: MonitoringDashboardService
    autoRefreshIntervalMs?: number
}>

function calculateRetryDelayMs(consecutiveFailures: number): number {
    return Math.min(
        RETRY_MAX_DELAY_MS,
        RETRY_BASE_DELAY_MS * (2 ** Math.max(0, consecutiveFailures - 1))
    )
}

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

export function getIsPageVisible(): boolean {
    const pageDocument = globalThis.document
    if (!pageDocument) {
        return true
    }
    return pageDocument.visibilityState === 'visible'
}

export function useMonitoringDashboardModel({
    monitoringService,
    autoRefreshIntervalMs = DEFAULT_AUTO_REFRESH_INTERVAL_MS,
}: UseMonitoringDashboardModelParams): MonitoringDashboardViewModel {
    const isDashboardRequestInFlightRef = useRef(false)
    const monitoringStreamRef = useRef<MonitoringStatsStreamHandle | null>(null)
    const consecutiveFailuresRef = useRef(0)
    const isMountedRef = useRef(true)
    const hasBootstrappedSnapshotRef = useRef(false)

    const [livePayload, setLivePayload] = useState<MonitoringLivePayload | null>(null)
    const [accessDecision, setAccessDecision] = useState<MonitoringAccessDecision | null>(null)
    const [readyPayload, setReadyPayload] = useState<MonitoringReadyPayload | null>(null)
    const [statsPayload, setStatsPayload] = useState<MonitoringStatsPayload | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [lastSuccessfulAtMs, setLastSuccessfulAtMs] = useState<number | null>(null)
    const [consecutiveFailures, setConsecutiveFailures] = useState(0)
    const [nextRetryAtMs, setNextRetryAtMs] = useState<number | null>(null)
    const [retryClockNowMs, setRetryClockNowMs] = useState(() => Date.now())
    const [isDataStale, setIsDataStale] = useState(false)
    const [isPageVisible, setIsPageVisible] = useState(getIsPageVisible)
    const [hasActiveStatsStream, setHasActiveStatsStream] = useState(false)

    const markSuccessfulLoad = useCallback((completedAtMs: number) => {
        consecutiveFailuresRef.current = 0
        setConsecutiveFailures(0)
        setNextRetryAtMs(null)
        setLastSuccessfulAtMs(completedAtMs)
        setRetryClockNowMs(completedAtMs)
        setIsDataStale(false)
    }, [])

    const stopMonitoringStatsStream = useCallback(() => {
        if (monitoringStreamRef.current) {
            monitoringStreamRef.current.close()
            monitoringStreamRef.current = null
        }
        if (!isMountedRef.current) {
            return
        }
        setHasActiveStatsStream(false)
    }, [])

    const scheduleRetry = useCallback((failedAtMs: number) => {
        consecutiveFailuresRef.current += 1
        const nextFailures = consecutiveFailuresRef.current
        setConsecutiveFailures(nextFailures)
        setNextRetryAtMs(failedAtMs + calculateRetryDelayMs(nextFailures))
        setRetryClockNowMs(failedAtMs)
    }, [])

    const loadWithAuthenticatedSnapshot = useCallback(async (
        getMonitoringAuthenticatedSnapshot: NonNullable<MonitoringDashboardService['getMonitoringAuthenticatedSnapshot']>,
    ): Promise<MonitoringAccessDecision> => {
        const [liveResponse, snapshot] = await Promise.all([
            monitoringService.getMonitoringLive(),
            getMonitoringAuthenticatedSnapshot(),
        ])

        if (!isMountedRef.current) {
            return snapshot.accessDecision
        }

        setLivePayload(liveResponse)
        setAccessDecision(snapshot.accessDecision)
        setReadyPayload(snapshot.readyPayload)
        setStatsPayload(snapshot.statsPayload)
        stopMonitoringStatsStream()
        markSuccessfulLoad(Date.now())
        return snapshot.accessDecision
    }, [markSuccessfulLoad, monitoringService, stopMonitoringStatsStream])

    const loadWithoutSnapshot = useCallback(async () => {
        const monitoringAuthToken = await getMonitoringAuthToken()
        const [liveResponse, accessResponse] = await Promise.all([
            monitoringService.getMonitoringLive(),
            monitoringService.getMonitoringAccess(monitoringAuthToken),
        ])

        if (!isMountedRef.current) {
            return ''
        }

        setLivePayload(liveResponse)
        setAccessDecision(accessResponse)

        if (!accessResponse.allowed) {
            setReadyPayload(null)
            setStatsPayload(null)
            stopMonitoringStatsStream()
            markSuccessfulLoad(Date.now())
            return ''
        }

        const readyResponse = await monitoringService.getMonitoringReady(monitoringAuthToken)
        if (!isMountedRef.current) {
            return ''
        }

        setReadyPayload(readyResponse)

        return monitoringAuthToken
    }, [markSuccessfulLoad, monitoringService, stopMonitoringStatsStream])

    const startMonitoringStatsStream = useCallback(async (
        monitoringAuthToken: string,
        getMonitoringStatsStream: NonNullable<MonitoringDashboardService['getMonitoringStatsStream']>,
    ) => {
        const streamPayloads = await getMonitoringStatsStream({
            accessToken: monitoringAuthToken,
            intervalSeconds: autoRefreshIntervalMs / 1000,
            onPayload: (payload) => {
                if (!isMountedRef.current) {
                    return
                }
                setStatsPayload(payload)
                markSuccessfulLoad(Date.now())
            },
            onError: (error) => {
                if (!isMountedRef.current) {
                    return
                }
                const isUnexpectedStreamClose = error.message === MONITORING_STREAM_UNEXPECTED_CLOSE_MESSAGE
                setErrorMessage(isUnexpectedStreamClose ? null : error.message)
                stopMonitoringStatsStream()
                scheduleRetry(Date.now())
            },
        })
        if (!isMountedRef.current) {
            streamPayloads.close()
            return
        }
        monitoringStreamRef.current = streamPayloads
        setHasActiveStatsStream(true)
    }, [autoRefreshIntervalMs, markSuccessfulLoad, scheduleRetry, stopMonitoringStatsStream])

    const loadMonitoringStatsSnapshot = useCallback(async (monitoringAuthToken: string) => {
        const statsResponse = await monitoringService.getMonitoringStats(monitoringAuthToken)
        if (!isMountedRef.current) {
            return
        }

        setStatsPayload(statsResponse)
    }, [monitoringService])

    const setLoadingStateForRequest = useCallback((isBackgroundRefresh: boolean) => {
        if (isBackgroundRefresh) {
            setIsRefreshing(true)
            return
        }
        setIsLoading(true)
    }, [])

    const tryBootstrapWithSnapshot = useCallback(async (isBackgroundRefresh: boolean): Promise<boolean> => {
        const getMonitoringAuthenticatedSnapshot = monitoringService.getMonitoringAuthenticatedSnapshot
        const shouldBootstrapWithSnapshot = !isBackgroundRefresh
            && !hasBootstrappedSnapshotRef.current
            && getMonitoringAuthenticatedSnapshot !== undefined
        if (!shouldBootstrapWithSnapshot) {
            return false
        }

        const accessFromSnapshot = await loadWithAuthenticatedSnapshot(getMonitoringAuthenticatedSnapshot)
        hasBootstrappedSnapshotRef.current = true
        if (!isMountedRef.current) {
            return true
        }
        if (!accessFromSnapshot.allowed) {
            return true
        }

        const getMonitoringStatsStream = monitoringService.getMonitoringStatsStream
        if (getMonitoringStatsStream !== undefined && monitoringStreamRef.current === null) {
            const monitoringAuthToken = await getMonitoringAuthToken()
            await startMonitoringStatsStream(
                monitoringAuthToken,
                getMonitoringStatsStream
            )
        }
        return true
    }, [loadWithAuthenticatedSnapshot, monitoringService, startMonitoringStatsStream])

    const loadStatsForAuthorizedRequest = useCallback(async (monitoringAuthToken: string) => {
        const getMonitoringStatsStream = monitoringService.getMonitoringStatsStream
        const shouldUseStream = getMonitoringStatsStream !== undefined
            && monitoringStreamRef.current === null
        if (shouldUseStream) {
            await startMonitoringStatsStream(
                monitoringAuthToken,
                getMonitoringStatsStream
            )
            return
        }

        if (monitoringStreamRef.current === null) {
            await loadMonitoringStatsSnapshot(monitoringAuthToken)
        }
    }, [loadMonitoringStatsSnapshot, monitoringService, startMonitoringStatsStream])

    const loadDashboard = useCallback(
        async (isBackgroundRefresh: boolean) => {
            if (isDashboardRequestInFlightRef.current) {
                return
            }
            isDashboardRequestInFlightRef.current = true
            setErrorMessage(null)
            setLoadingStateForRequest(isBackgroundRefresh)

            try {
                const bootstrappedWithSnapshot = await tryBootstrapWithSnapshot(isBackgroundRefresh)
                if (bootstrappedWithSnapshot) {
                    return
                }

                const monitoringAuthToken = await loadWithoutSnapshot()
                if (!monitoringAuthToken) {
                    return
                }
                await loadStatsForAuthorizedRequest(monitoringAuthToken)
                if (!isMountedRef.current) {
                    return
                }

                markSuccessfulLoad(Date.now())
            } catch (error) {
                if (!isMountedRef.current) {
                    return
                }

                const failedAtMs = Date.now()
                setReadyPayload(null)
                setStatsPayload(null)
                stopMonitoringStatsStream()
                setErrorMessage(error instanceof Error ? error.message : 'Failed to load monitoring data.')
                scheduleRetry(failedAtMs)
            } finally {
                if (isMountedRef.current) {
                    setIsLoading(false)
                    setIsRefreshing(false)
                }
                isDashboardRequestInFlightRef.current = false
            }
        },
        [
            loadWithoutSnapshot,
            loadStatsForAuthorizedRequest,
            markSuccessfulLoad,
            setLoadingStateForRequest,
            stopMonitoringStatsStream,
            scheduleRetry,
            tryBootstrapWithSnapshot,
        ]
    )

    useEffect(() => {
        void loadDashboard(false)
    }, [loadDashboard])

    useEffect(() => {
        if (!globalThis.document) {
            return
        }
        const visibilityDocument = globalThis.document

        const handleVisibilityChange = () => {
            const nextVisible = getIsPageVisible()
            setIsPageVisible(nextVisible)
            if (!nextVisible) {
                stopMonitoringStatsStream()
            }

            if (nextVisible) {
                void loadDashboard(true)
            }
        }

        visibilityDocument.addEventListener('visibilitychange', handleVisibilityChange)
        return () => {
            visibilityDocument.removeEventListener('visibilitychange', handleVisibilityChange)
        }
    }, [loadDashboard, stopMonitoringStatsStream])

    useEffect(() => {
        if (!isPageVisible || hasActiveStatsStream) {
            return
        }

        const intervalId = globalThis.setInterval(() => {
            const nowMs = Date.now()
            if (nextRetryAtMs !== null && nowMs < nextRetryAtMs) {
                return
            }
            void loadDashboard(true)
        }, autoRefreshIntervalMs)
        return () => {
            globalThis.clearInterval(intervalId)
        }
    }, [autoRefreshIntervalMs, hasActiveStatsStream, isPageVisible, loadDashboard, nextRetryAtMs])

    useEffect(() => {
        if (nextRetryAtMs === null || !isPageVisible) {
            return
        }

        const delayMs = Math.max(0, nextRetryAtMs - Date.now())
        const retryTimeoutId = globalThis.setTimeout(() => {
            void loadDashboard(true)
        }, delayMs)

        return () => {
            globalThis.clearTimeout(retryTimeoutId)
        }
    }, [isPageVisible, loadDashboard, nextRetryAtMs])

    useEffect(() => {
        if (nextRetryAtMs === null) {
            return
        }

        const tick = () => {
            setRetryClockNowMs(Date.now())
        }

        tick()
        const clockId = globalThis.setInterval(tick, RETRY_TICK_INTERVAL_MS)

        return () => {
            globalThis.clearInterval(clockId)
        }
    }, [nextRetryAtMs])

    useEffect(() => {
        isMountedRef.current = true
        return () => {
            isMountedRef.current = false
            stopMonitoringStatsStream()
        }
    }, [stopMonitoringStatsStream])

    const eventRows = useMemo<EventRow[]>(() => {
        if (!statsPayload) {
            return []
        }

        const flattened = Object.entries(statsPayload.events).flatMap(([eventName, outcomes]) =>
            Object.entries(outcomes).map(([outcome, count]) => ({
                eventName,
                outcome,
                count,
            }))
        )

        flattened.sort((a, b) => b.count - a.count || a.eventName.localeCompare(b.eventName))
        return flattened
    }, [statsPayload])

    const visibleRoutes = useMemo(() => (
        statsPayload
            ? monitoringRouteVisibilityPolicy.filterVisibleRoutes(statsPayload.routes)
            : []
    ), [statsPayload])

    const maxRouteRequests = useMemo(() => {
        if (visibleRoutes.length === 0) {
            return 1
        }

        return visibleRoutes.reduce(
            (maxRequests, routeRow) => Math.max(maxRequests, routeRow.total_requests),
            1
        )
    }, [visibleRoutes])

    const maxEventCount = useMemo(() => {
        if (eventRows.length === 0) {
            return 1
        }

        return eventRows.reduce(
            (maxCount, eventRow) => Math.max(maxCount, eventRow.count),
            1
        )
    }, [eventRows])

    const routeSummaryRows = useMemo<RouteSummaryRow[]>(() => (
        visibleRoutes
            .slice(0, MAX_ROUTE_SUMMARY_ROWS)
            .map((routeRow) => ({
                route: routeRow.route,
                method: routeRow.method,
                totalRequests: routeRow.total_requests,
                totalErrors: routeRow.total_errors,
                avgLatencyMs: routeRow.avg_latency_ms,
                requestWidth: calculateBarWidth(routeRow.total_requests, maxRouteRequests),
            }))
    ), [maxRouteRequests, visibleRoutes])

    const authEventSummaryRows = useMemo<AuthEventSummaryRow[]>(() => (
        eventRows
            .slice(0, MAX_AUTH_EVENT_SUMMARY_ROWS)
            .map((eventRow) => ({
                ...eventRow,
                eventWidth: calculateBarWidth(eventRow.count, maxEventCount),
            }))
    ), [eventRows, maxEventCount])

    const timeseriesPoints = useMemo(() => {
        const points = statsPayload?.timeseries?.points ?? []
        const validPoints = points.filter((point) => point !== null && point !== undefined)
        return validPoints.slice(-MAX_REALTIME_LATENCY_TICKS)
    }, [statsPayload])

    const rawRealtimeWindowSeconds = statsPayload?.timeseries?.window_seconds ?? 0
    const realtimeBucketSeconds = statsPayload?.timeseries?.bucket_seconds ?? 0
    const hasRealtimeSeries = timeseriesPoints.length > 0
    const realtimeWindowSeconds = useMemo(() => {
        if (!hasRealtimeSeries || realtimeBucketSeconds <= 0) {
            return rawRealtimeWindowSeconds
        }

        const renderedWindowSeconds = realtimeBucketSeconds * timeseriesPoints.length
        if (rawRealtimeWindowSeconds <= 0) {
            return renderedWindowSeconds
        }

        return Math.min(rawRealtimeWindowSeconds, renderedWindowSeconds)
    }, [hasRealtimeSeries, rawRealtimeWindowSeconds, realtimeBucketSeconds, timeseriesPoints.length])

    const realtimeTotals = useMemo<RealtimeTotals>(() => {
        if (timeseriesPoints.length === 0) {
            return null
        }
        const totals = timeseriesPoints.reduce(
            (nextTotals, point) => ({
                requests: nextTotals.requests + point.requests,
                errors: nextTotals.errors + point.errors,
            }),
            { requests: 0, errors: 0 }
        )
        return {
            requests: totals.requests,
            errors: totals.errors,
            errorRate: totals.requests > 0 ? totals.errors / totals.requests : 0,
        }
    }, [timeseriesPoints])

    const latencySeries = useMemo<LatencySeriesPoint[]>(() => {
        if (timeseriesPoints.length > 0) {
            return timeseriesPoints.map((point, index) => ({
                id: index + 1,
                label: formatTimeLabel(point.timestamp),
                value: point.avg_latency_ms,
                requests: point.requests,
            }))
        }

        if (!statsPayload) {
            return []
        }

        return visibleRoutes
            .slice(0, 8)
            .map((routeRow, index) => ({
                id: index + 1,
                label: routeRow.route,
                value: routeRow.avg_latency_ms,
                requests: routeRow.total_requests,
            }))
    }, [statsPayload, timeseriesPoints, visibleRoutes])

    const latencyChart = useMemo<LatencyChartModel>(() => {
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
        const maxLatency = latencySeries.reduce(
            (nextMaxLatency, entry) => Math.max(nextMaxLatency, entry.value),
            1
        )
        const maxRequests = latencySeries.reduce(
            (nextMaxRequests, entry) => Math.max(nextMaxRequests, entry.requests ?? 0),
            0
        )

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
    }, [hasRealtimeSeries, latencySeries])

    const errorRateMeter = useMemo<ErrorRateMeter>(() => {
        const sourceErrorRate = realtimeTotals?.errorRate ?? statsPayload?.totals.error_rate ?? 0
        const errorRate = clamp(sourceErrorRate, 0, 1)
        const meterPercent = errorRate * 100
        const progressLength = 251.2 * errorRate
        const colorClass = errorRate <= 0.05 ? 'text-blue-600' : 'text-red-700'

        return {
            percentText: `${meterPercent.toFixed(2)}%`,
            progressLength,
            colorClass,
        }
    }, [statsPayload, realtimeTotals])

    const readinessMeter = useMemo<ReadinessMeter>(() => {
        if (!readyPayload || readyPayload.checks.length === 0) {
            return {
                percentText: '--',
                progressLength: 0,
                colorClass: 'text-gray-600',
                healthyChecks: 0,
                totalChecks: 0,
            }
        }

        const healthyChecks = readyPayload.checks.filter((check) => check.status.toLowerCase() === 'ok').length
        const totalChecks = readyPayload.checks.length
        const readinessRate = clamp(healthyChecks / totalChecks, 0, 1)
        const progressLength = 251.2 * readinessRate

        return {
            percentText: `${(readinessRate * 100).toFixed(0)}%`,
            progressLength,
            colorClass: readinessRate >= 0.8 ? 'text-blue-600' : 'text-red-700',
            healthyChecks,
            totalChecks,
        }
    }, [readyPayload])

    useEffect(() => {
        if (lastSuccessfulAtMs === null) {
            setIsDataStale(false)
            return
        }

        const staleThresholdMs = Math.max(
            MIN_STALE_THRESHOLD_MS,
            autoRefreshIntervalMs * STALE_THRESHOLD_MULTIPLIER
        )
        const markStaleAtMs = lastSuccessfulAtMs + staleThresholdMs
        const nowMs = Date.now()

        if (nowMs >= markStaleAtMs) {
            setIsDataStale(true)
            return
        }

        setIsDataStale(false)
        const staleTimeoutId = globalThis.setTimeout(() => {
            setIsDataStale(true)
        }, markStaleAtMs - nowMs)

        return () => {
            globalThis.clearTimeout(staleTimeoutId)
        }
    }, [autoRefreshIntervalMs, lastSuccessfulAtMs])

    const retryInSeconds = nextRetryAtMs === null
        ? 0
        : Math.max(0, Math.ceil((nextRetryAtMs - retryClockNowMs) / 1000))

    const lastSync = livePayload?.timestamp ?? statsPayload?.generated_at ?? ''

    const refreshDashboard = useCallback(() => {
        void loadDashboard(true)
    }, [loadDashboard])

    return {
        livePayload,
        accessDecision,
        readyPayload,
        statsPayload,
        isLoading,
        isRefreshing,
        errorMessage,
        consecutiveFailures,
        retryInSeconds,
        nextRetryAtMs,
        isDataStale,
        lastSync,
        hasRealtimeSeries,
        realtimeWindowSeconds,
        realtimeBucketSeconds,
        realtimeTotals,
        eventRows,
        authEventSummaryRows,
        maxEventCount,
        visibleRoutes,
        routeSummaryRows,
        maxRouteRequests,
        latencySeries,
        latencyChart,
        errorRateMeter,
        readinessMeter,
        refreshDashboard,
    }
}
