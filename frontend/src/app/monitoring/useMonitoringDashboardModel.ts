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
    ErrorRateMeter,
    EventRow,
    LatencyChartModel,
    LatencySeriesPoint,
    ReadinessMeter,
    RealtimeTotals,
} from './monitoringViewModelTypes'
import { getMonitoringAuthToken } from '@/services/monitoring'

const DEFAULT_AUTO_REFRESH_INTERVAL_MS = 5000
const STALE_THRESHOLD_MULTIPLIER = 3
const MIN_STALE_THRESHOLD_MS = 15000
const RETRY_BASE_DELAY_MS = 2000
const RETRY_MAX_DELAY_MS = 30000
const RETRY_TICK_INTERVAL_MS = 1000

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
    maxEventCount: number
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
    ) => {
        const [liveResponse, snapshot] = await Promise.all([
            monitoringService.getMonitoringLive(),
            getMonitoringAuthenticatedSnapshot(),
        ])

        setLivePayload(liveResponse)
        setAccessDecision(snapshot.accessDecision)
        setReadyPayload(snapshot.readyPayload)
        setStatsPayload(snapshot.statsPayload)
        stopMonitoringStatsStream()
        markSuccessfulLoad(Date.now())
    }, [markSuccessfulLoad, monitoringService, stopMonitoringStatsStream])

    const loadWithoutSnapshot = useCallback(async () => {
        const monitoringAuthToken = await getMonitoringAuthToken()
        const [liveResponse, accessResponse] = await Promise.all([
            monitoringService.getMonitoringLive(),
            monitoringService.getMonitoringAccess(monitoringAuthToken),
        ])

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
                setStatsPayload(payload)
                markSuccessfulLoad(Date.now())
            },
            onError: (error) => {
                if (!isMountedRef.current) {
                    return
                }
                setErrorMessage(error.message)
                stopMonitoringStatsStream()
                scheduleRetry(Date.now())
            },
        })
        monitoringStreamRef.current = streamPayloads
    }, [autoRefreshIntervalMs, markSuccessfulLoad, scheduleRetry, stopMonitoringStatsStream])

    const loadMonitoringStatsSnapshot = useCallback(async (monitoringAuthToken: string) => {
        const statsResponse = await monitoringService.getMonitoringStats(monitoringAuthToken)
        setStatsPayload(statsResponse)
    }, [monitoringService])

    const loadDashboard = useCallback(
        async (isBackgroundRefresh: boolean) => {
            if (isDashboardRequestInFlightRef.current) {
                return
            }
            isDashboardRequestInFlightRef.current = true
            setErrorMessage(null)

            if (isBackgroundRefresh) {
                setIsRefreshing(true)
            } else {
                setIsLoading(true)
        }

        try {
                if (monitoringService.getMonitoringAuthenticatedSnapshot) {
                    await loadWithAuthenticatedSnapshot(monitoringService.getMonitoringAuthenticatedSnapshot)
                    return
                }

                const monitoringAuthToken = await loadWithoutSnapshot()
                if (!monitoringAuthToken) {
                    return
                }

                const getMonitoringStatsStream = monitoringService.getMonitoringStatsStream
                const shouldUseStream = getMonitoringStatsStream !== undefined
                    && monitoringStreamRef.current === null
                if (shouldUseStream) {
                    await startMonitoringStatsStream(
                        monitoringAuthToken,
                        getMonitoringStatsStream
                    )
                } else {
                    await loadMonitoringStatsSnapshot(monitoringAuthToken)
                }

                markSuccessfulLoad(Date.now())
            } catch (error) {
                const failedAtMs = Date.now()
                setReadyPayload(null)
                setStatsPayload(null)
                stopMonitoringStatsStream()
                setErrorMessage(error instanceof Error ? error.message : 'Failed to load monitoring data.')
                scheduleRetry(failedAtMs)
            } finally {
                setIsLoading(false)
                setIsRefreshing(false)
                isDashboardRequestInFlightRef.current = false
            }
        },
        [
            loadWithAuthenticatedSnapshot,
            loadWithoutSnapshot,
            loadMonitoringStatsSnapshot,
            markSuccessfulLoad,
            monitoringService,
            startMonitoringStatsStream,
            stopMonitoringStatsStream,
            scheduleRetry,
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
        if (!isPageVisible) {
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
    }, [autoRefreshIntervalMs, isPageVisible, loadDashboard, nextRetryAtMs])

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

    const maxRouteRequests = useMemo(() => {
        if (!statsPayload || statsPayload.routes.length === 0) {
            return 1
        }

        return Math.max(
            1,
            ...statsPayload.routes.map((routeRow) => routeRow.total_requests)
        )
    }, [statsPayload])

    const maxEventCount = useMemo(() => {
        if (eventRows.length === 0) {
            return 1
        }

        return Math.max(1, ...eventRows.map((eventRow) => eventRow.count))
    }, [eventRows])

    const timeseriesPoints = useMemo(() => {
        const points = statsPayload?.timeseries?.points ?? []
        return points.filter((point) => point !== null && point !== undefined)
    }, [statsPayload])

    const realtimeWindowSeconds = statsPayload?.timeseries?.window_seconds ?? 0
    const realtimeBucketSeconds = statsPayload?.timeseries?.bucket_seconds ?? 0
    const hasRealtimeSeries = timeseriesPoints.length > 0

    const realtimeTotals = useMemo<RealtimeTotals>(() => {
        if (timeseriesPoints.length === 0) {
            return null
        }
        const requests = timeseriesPoints.reduce((sum, point) => sum + point.requests, 0)
        const errors = timeseriesPoints.reduce((sum, point) => sum + point.errors, 0)
        return {
            requests,
            errors,
            errorRate: requests > 0 ? errors / requests : 0,
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

        return statsPayload.routes
            .slice(0, 8)
            .map((routeRow, index) => ({
                id: index + 1,
                label: routeRow.route,
                value: routeRow.avg_latency_ms,
                requests: routeRow.total_requests,
            }))
    }, [statsPayload, timeseriesPoints])

    const latencyChart = useMemo<LatencyChartModel>(() => {
        if (latencySeries.length === 0) {
            return {
                linePoints: '',
                areaPath: '',
                maxLatency: 0,
            }
        }

        const width = 520
        const height = 220
        const paddingX = 26
        const topPadding = 16
        const bottomPadding = 30
        const plotWidth = width - paddingX * 2
        const plotHeight = height - topPadding - bottomPadding
        const maxLatency = Math.max(1, ...latencySeries.map((entry) => entry.value))

        const points = latencySeries.map((entry, index) => {
            const normalizedX = latencySeries.length === 1 ? 0.5 : index / (latencySeries.length - 1)
            const normalizedY = clamp(entry.value / maxLatency, 0, 1)

            const x = paddingX + normalizedX * plotWidth
            const y = topPadding + (1 - normalizedY) * plotHeight
            return { x, y }
        })

        const linePoints = points.map((point) => `${point.x},${point.y}`).join(' ')
        const firstPoint = points.at(0)!
        const lastPoint = points.at(-1)!
        const polylinePoints = points.map((point) => `${point.x} ${point.y}`).join(' L ')
        const areaPath = `M ${firstPoint.x} ${height - bottomPadding} L ${polylinePoints} L ${lastPoint.x} ${height - bottomPadding} Z`

        return {
            linePoints,
            areaPath,
            maxLatency,
        }
    }, [latencySeries])

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
        maxEventCount,
        maxRouteRequests,
        latencySeries,
        latencyChart,
        errorRateMeter,
        readinessMeter,
        refreshDashboard,
    }
}
