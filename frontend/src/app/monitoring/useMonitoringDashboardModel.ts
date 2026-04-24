import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
    MonitoringAccessDecision,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
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

const DEFAULT_AUTO_REFRESH_INTERVAL_MS = 5000

export type MonitoringDashboardService = {
    getMonitoringLive: () => Promise<MonitoringLivePayload>
    getMonitoringAccess: () => Promise<MonitoringAccessDecision>
    getMonitoringReady: () => Promise<MonitoringReadyPayload>
    getMonitoringStats: () => Promise<MonitoringStatsPayload>
}

export type MonitoringDashboardViewModel = {
    livePayload: MonitoringLivePayload | null
    accessDecision: MonitoringAccessDecision | null
    readyPayload: MonitoringReadyPayload | null
    statsPayload: MonitoringStatsPayload | null
    isLoading: boolean
    isRefreshing: boolean
    errorMessage: string | null
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

type UseMonitoringDashboardModelParams = {
    monitoringService: MonitoringDashboardService
    autoRefreshIntervalMs?: number
}

export function useMonitoringDashboardModel({
    monitoringService,
    autoRefreshIntervalMs = DEFAULT_AUTO_REFRESH_INTERVAL_MS,
}: UseMonitoringDashboardModelParams): MonitoringDashboardViewModel {
    const isDashboardRequestInFlightRef = useRef(false)
    const [livePayload, setLivePayload] = useState<MonitoringLivePayload | null>(null)
    const [accessDecision, setAccessDecision] = useState<MonitoringAccessDecision | null>(null)
    const [readyPayload, setReadyPayload] = useState<MonitoringReadyPayload | null>(null)
    const [statsPayload, setStatsPayload] = useState<MonitoringStatsPayload | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
                const [liveResponse, accessResponse] = await Promise.all([
                    monitoringService.getMonitoringLive(),
                    monitoringService.getMonitoringAccess(),
                ])

                setLivePayload(liveResponse)
                setAccessDecision(accessResponse)

                if (!accessResponse.allowed) {
                    setReadyPayload(null)
                    setStatsPayload(null)
                    return
                }

                const [readyResponse, statsResponse] = await Promise.all([
                    monitoringService.getMonitoringReady(),
                    monitoringService.getMonitoringStats(),
                ])
                setReadyPayload(readyResponse)
                setStatsPayload(statsResponse)
            } catch (error) {
                setReadyPayload(null)
                setStatsPayload(null)
                setErrorMessage(error instanceof Error ? error.message : 'Failed to load monitoring data.')
            } finally {
                setIsLoading(false)
                setIsRefreshing(false)
                isDashboardRequestInFlightRef.current = false
            }
        },
        [monitoringService]
    )

    useEffect(() => {
        void loadDashboard(false)
        const intervalId = window.setInterval(() => {
            void loadDashboard(true)
        }, autoRefreshIntervalMs)
        return () => {
            window.clearInterval(intervalId)
        }
    }, [autoRefreshIntervalMs, loadDashboard])

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
        return statsPayload?.timeseries?.points ?? []
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
        const first = points[0]
        const last = points[points.length - 1]
        const areaPath = `M ${first.x} ${height - bottomPadding} L ${points
            .map((point) => `${point.x} ${point.y}`)
            .join(' L ')} L ${last.x} ${height - bottomPadding} Z`

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

