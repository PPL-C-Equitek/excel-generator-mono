'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from '@/components/Sidebar'
import {
    getMonitoringAccess,
    getMonitoringLive,
    getMonitoringReady,
    getMonitoringStats,
    type MonitoringAccessDecision,
    type MonitoringLivePayload,
    type MonitoringReadyPayload,
    type MonitoringStatsPayload,
} from '@/services/monitoring'

type MonitoringDashboardService = {
    getMonitoringLive: () => Promise<MonitoringLivePayload>
    getMonitoringAccess: () => Promise<MonitoringAccessDecision>
    getMonitoringReady: () => Promise<MonitoringReadyPayload>
    getMonitoringStats: () => Promise<MonitoringStatsPayload>
}

type MonitoringPageProps = {
    readonly monitoringService?: MonitoringDashboardService
}

const defaultMonitoringService: MonitoringDashboardService = {
    getMonitoringLive,
    getMonitoringAccess,
    getMonitoringReady,
    getMonitoringStats,
}

const ACCESS_REASON_MESSAGES: Record<string, string> = {
    unauthenticated: 'Please log in to continue.',
    unverified: 'A verified account is required to access monitoring.',
    no_account: 'Monitoring account access is required for this page.',
    inactive: 'Your monitoring account is currently inactive.',
    ok: 'Monitoring access granted.',
}
const AUTO_REFRESH_INTERVAL_MS = 5000

function formatTimestamp(value: string): string {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return value
    }

    return parsed.toLocaleString('en-US', {
        hour12: false,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    })
}

function formatPercent(value: number): string {
    if (!Number.isFinite(value)) {
        return '0.00%'
    }

    return `${(value * 100).toFixed(2)}%`
}

function formatTimeLabel(value: string): string {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return value
    }
    return parsed.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    })
}

function statusBadgeClass(status: string): string {
    const normalizedStatus = status.toLowerCase()
    if (normalizedStatus === 'ok' || normalizedStatus === 'success') {
        return 'border border-blue-200 bg-blue-50 text-blue-700'
    }
    if (normalizedStatus === 'degraded') {
        return 'border border-red-300 bg-red-50 text-red-700'
    }
    if (normalizedStatus === 'down' || normalizedStatus === 'error' || normalizedStatus === 'exception') {
        return 'border border-red-400 bg-red-50 text-red-700'
    }
    return 'border border-gray-300 bg-gray-100 text-gray-700'
}

function resolveAccessMessage(reason: string): string {
    return ACCESS_REASON_MESSAGES[reason] ?? `Access status: ${reason}`
}

function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value))
}

export default function MonitoringPage({ monitoringService = defaultMonitoringService }: MonitoringPageProps) {
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
        }, AUTO_REFRESH_INTERVAL_MS)
        return () => {
            window.clearInterval(intervalId)
        }
    }, [loadDashboard])

    const eventRows = useMemo(() => {
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

    const realtimeTotals = useMemo(() => {
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

    const latencySeries = useMemo(() => {
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

    const latencyChart = useMemo(() => {
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

    const errorRateMeter = useMemo(() => {
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

    const readinessMeter = useMemo(() => {
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

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="monitoring" />
            <main className="ml-56 flex-1 bg-gray-50 px-4 py-8 sm:px-6 lg:px-10">
                <div className="mx-auto max-w-7xl space-y-6">
                    <section className="rounded-2xl border border-gray-700/40 bg-gradient-to-br from-gray-950 via-gray-900 to-gray-800 p-6 shadow-xl">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div className="space-y-3">
                                <span className="inline-flex rounded-full border border-red-300/30 bg-red-700/20 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-red-200">
                                    Monitoring
                                </span>
                                <div>
                                    <h1 className="text-2xl font-bold tracking-tight text-white">System Monitoring</h1>
                                    <p className="mt-2 max-w-2xl text-sm text-gray-300">
                                        Grafana-inspired live health, readiness, traffic, and auth activity for your backend.
                                    </p>
                                </div>
                            </div>

                            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                                <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-gray-200">
                                    Last sync: <span className="font-semibold text-white">{lastSync ? formatTimestamp(lastSync) : '--'}</span>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => {
                                        void loadDashboard(true)
                                    }}
                                    disabled={isLoading || isRefreshing}
                                    className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-all duration-150 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {isRefreshing ? 'Refreshing...' : 'Refresh Monitoring'}
                                </button>
                            </div>
                        </div>
                    </section>

                    {errorMessage ? (
                        <div
                            role="alert"
                            className="flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
                        >
                            <span aria-hidden>!</span>
                            <span>{errorMessage}</span>
                        </div>
                    ) : null}

                    {isLoading ? (
                        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-md">
                            <div className="animate-pulse space-y-3">
                                <div className="h-4 w-1/4 rounded bg-gray-200" />
                                <div className="h-4 w-1/2 rounded bg-gray-200" />
                                <div className="h-4 w-3/4 rounded bg-gray-200" />
                            </div>
                        </section>
                    ) : null}

                    {!isLoading && livePayload && accessDecision ? (
                        <>
                            <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md">
                                <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                    <h2 className="text-lg font-semibold text-gray-900">Traffic Summary</h2>
                                    {statsPayload ? (
                                        <p className="text-sm text-gray-500">
                                            Generated: {formatTimestamp(statsPayload.generated_at)}
                                        </p>
                                    ) : null}
                                </div>

                                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                                    <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                                        <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Live Status</p>
                                        <p className={`mt-3 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${statusBadgeClass(livePayload.status)}`}>
                                            {livePayload.status}
                                        </p>
                                        <p className="mt-3 text-sm text-gray-600">{formatTimestamp(livePayload.timestamp)}</p>
                                    </article>

                                    <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                                        <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Access</p>
                                        <p className={`mt-3 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${statusBadgeClass(accessDecision.allowed ? 'success' : 'error')}`}>
                                            {accessDecision.allowed ? 'allowed' : 'denied'}
                                        </p>
                                        <p className="mt-3 text-sm text-gray-600">{resolveAccessMessage(accessDecision.reason)}</p>
                                    </article>

                                    <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                                        <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Total Requests</p>
                                        <p className="mt-2 text-3xl font-bold text-gray-900">
                                            {statsPayload ? (realtimeTotals?.requests ?? statsPayload.totals.requests) : '--'}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            {hasRealtimeSeries && realtimeWindowSeconds > 0
                                                ? `Last ${realtimeWindowSeconds}s window`
                                                : 'Backend traffic volume'}
                                        </p>
                                    </article>

                                    <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                                        <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Errors</p>
                                        <p className="mt-2 text-3xl font-bold text-red-700">
                                            {statsPayload ? (realtimeTotals?.errors ?? statsPayload.totals.errors) : '--'}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            Error rate:{' '}
                                            {statsPayload
                                                ? formatPercent(realtimeTotals?.errorRate ?? statsPayload.totals.error_rate)
                                                : '--'}
                                        </p>
                                    </article>
                                </div>
                            </section>

                            {!accessDecision.allowed ? (
                                <section className="rounded-2xl border border-red-300 bg-red-50 p-5 shadow-md">
                                    <h3 className="text-base font-semibold text-red-700">Monitoring Access Required</h3>
                                    <p className="mt-2 text-sm text-red-700">
                                        {resolveAccessMessage(accessDecision.reason)}
                                    </p>
                                </section>
                            ) : null}

                            {accessDecision.allowed && statsPayload ? (
                                <section className="space-y-4">
                                    <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                                        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
                                            <div className="flex items-center justify-between gap-3">
                                                <h3 className="text-base font-semibold text-gray-900">Latency Line Chart</h3>
                                                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">
                                                    {hasRealtimeSeries ? `Realtime ${realtimeBucketSeconds}s Buckets` : 'Avg Route Latency'}
                                                </span>
                                            </div>

                                            {latencySeries.length === 0 ? (
                                                <p className="mt-4 text-sm text-gray-600">No latency data available yet.</p>
                                            ) : (
                                                <>
                                                    <div className="mt-4 overflow-x-auto rounded-xl border border-gray-200 bg-gray-50 p-3">
                                                        <svg
                                                            viewBox="0 0 520 220"
                                                            className="h-52 w-full min-w-[520px]"
                                                            role="img"
                                                            aria-label="Latency trend line chart"
                                                        >
                                                            <line x1="26" y1="190" x2="494" y2="190" stroke="#d1d5db" strokeWidth="1" />
                                                            <line x1="26" y1="16" x2="26" y2="190" stroke="#d1d5db" strokeWidth="1" />
                                                            {latencyChart.areaPath ? (
                                                                <path
                                                                    d={latencyChart.areaPath}
                                                                    fill="#dbeafe"
                                                                    fillOpacity="0.6"
                                                                />
                                                            ) : null}
                                                            {latencyChart.linePoints ? (
                                                                <polyline
                                                                    points={latencyChart.linePoints}
                                                                    fill="none"
                                                                    stroke="#2563eb"
                                                                    strokeWidth="3"
                                                                    strokeLinecap="round"
                                                                    strokeLinejoin="round"
                                                                />
                                                            ) : null}
                                                            {latencySeries.map((entry, index) => {
                                                                const normalizedX = latencySeries.length === 1 ? 0.5 : index / (latencySeries.length - 1)
                                                                const normalizedY = clamp(entry.value / Math.max(1, latencyChart.maxLatency), 0, 1)
                                                                const x = 26 + normalizedX * (520 - 52)
                                                                const y = 16 + (1 - normalizedY) * (220 - 46)
                                                                const showLabel = latencySeries.length <= 6 || index % 2 === 0 || index === latencySeries.length - 1
                                                                const xLabel = hasRealtimeSeries ? entry.label : String(entry.id)

                                                                return (
                                                                    <g key={entry.id}>
                                                                        <circle cx={x} cy={y} r="4" fill="#2563eb" />
                                                                        <text
                                                                            x={x}
                                                                            y="208"
                                                                            textAnchor="middle"
                                                                            fontSize="11"
                                                                            fill="#6b7280"
                                                                        >
                                                                            {showLabel ? xLabel : ''}
                                                                        </text>
                                                                    </g>
                                                                )
                                                            })}
                                                        </svg>
                                                    </div>

                                                    <p className="mt-3 text-sm text-gray-600">
                                                        {hasRealtimeSeries && realtimeWindowSeconds > 0 ? (
                                                            <>
                                                                Peak latency in last {realtimeWindowSeconds}s:{' '}
                                                                <span className="font-semibold text-gray-900">{latencyChart.maxLatency.toFixed(2)} ms</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                Peak observed latency in this snapshot:{' '}
                                                                <span className="font-semibold text-gray-900">{latencyChart.maxLatency.toFixed(2)} ms</span>
                                                            </>
                                                        )}
                                                    </p>
                                                    {hasRealtimeSeries ? (
                                                        <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                                                            Latest bucket {latencySeries[latencySeries.length - 1]?.label}: avg latency{' '}
                                                            <span className="font-semibold text-gray-900">
                                                                {latencySeries[latencySeries.length - 1]?.value.toFixed(2)} ms
                                                            </span>{' '}
                                                            across{' '}
                                                            <span className="font-semibold text-gray-900">
                                                                {latencySeries[latencySeries.length - 1]?.requests ?? 0}
                                                            </span>{' '}
                                                            requests.
                                                        </div>
                                                    ) : (
                                                        <ul className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-600 sm:grid-cols-2">
                                                            {latencySeries.map((entry) => (
                                                                <li key={entry.id} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
                                                                    <span className="font-semibold text-gray-900">[{entry.id}]</span> {entry.label}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    )}
                                                </>
                                            )}
                                        </article>

                                        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-4">
                                            <h3 className="text-base font-semibold text-gray-900">Meter Panels</h3>

                                            <div className="mt-4 grid grid-cols-1 gap-4">
                                                <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
                                                    <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Error Rate Meter</p>
                                                    <div className="mt-2 flex items-center gap-3">
                                                        <svg viewBox="0 0 200 120" className="h-24 w-28" role="img" aria-label="Error rate meter">
                                                            <path
                                                                d="M20 100 A80 80 0 0 1 180 100"
                                                                fill="none"
                                                                stroke="#e5e7eb"
                                                                strokeWidth="12"
                                                                strokeLinecap="round"
                                                            />
                                                            <path
                                                                d="M20 100 A80 80 0 0 1 180 100"
                                                                fill="none"
                                                                stroke="#b91c1c"
                                                                strokeWidth="12"
                                                                strokeLinecap="round"
                                                                strokeDasharray={`${errorRateMeter.progressLength} 251.2`}
                                                            />
                                                        </svg>
                                                        <div>
                                                            <p className={`text-2xl font-bold ${errorRateMeter.colorClass}`}>{errorRateMeter.percentText}</p>
                                                            <p className="text-xs text-gray-500">
                                                                {hasRealtimeSeries && realtimeWindowSeconds > 0
                                                                    ? `Window ${realtimeWindowSeconds}s`
                                                                    : 'Target < 5%'}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
                                                    <p className="text-xs uppercase tracking-[0.12em] text-gray-500">Readiness Meter</p>
                                                    <div className="mt-2 flex items-center gap-3">
                                                        <svg viewBox="0 0 200 120" className="h-24 w-28" role="img" aria-label="Readiness meter">
                                                            <path
                                                                d="M20 100 A80 80 0 0 1 180 100"
                                                                fill="none"
                                                                stroke="#e5e7eb"
                                                                strokeWidth="12"
                                                                strokeLinecap="round"
                                                            />
                                                            <path
                                                                d="M20 100 A80 80 0 0 1 180 100"
                                                                fill="none"
                                                                stroke="#2563eb"
                                                                strokeWidth="12"
                                                                strokeLinecap="round"
                                                                strokeDasharray={`${readinessMeter.progressLength} 251.2`}
                                                            />
                                                        </svg>
                                                        <div>
                                                            <p className={`text-2xl font-bold ${readinessMeter.colorClass}`}>{readinessMeter.percentText}</p>
                                                            <p className="text-xs text-gray-500">
                                                                Healthy checks: {readinessMeter.healthyChecks}/{readinessMeter.totalChecks}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
                                        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
                                            <h3 className="text-base font-semibold text-gray-900">Top Routes</h3>
                                            {statsPayload.routes.length === 0 ? (
                                                <p className="mt-3 text-sm text-gray-600">No route metrics available yet.</p>
                                            ) : (
                                                <div className="mt-4 space-y-3">
                                                    {statsPayload.routes.slice(0, 6).map((routeRow) => {
                                                        const requestWidth = `${Math.max(
                                                            8,
                                                            Math.round((routeRow.total_requests / maxRouteRequests) * 100)
                                                        )}%`

                                                        return (
                                                            <div key={`${routeRow.route}:${routeRow.method}`} className="rounded-xl border border-gray-200 bg-gray-50 p-3">
                                                                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                                                    <div>
                                                                        <p className="font-semibold text-gray-900">{routeRow.route}</p>
                                                                        <p className="text-xs text-gray-500">
                                                                            {routeRow.method} - avg latency {routeRow.avg_latency_ms.toFixed(2)} ms
                                                                        </p>
                                                                    </div>
                                                                    <div className="text-right text-sm">
                                                                        <p className="font-semibold text-gray-900">{routeRow.total_requests} req</p>
                                                                        <p className="text-red-700">{routeRow.total_errors} errors</p>
                                                                    </div>
                                                                </div>
                                                                <div className="mt-3 h-2 rounded-full bg-gray-200">
                                                                    <div
                                                                        className="h-2 rounded-full bg-blue-600 transition-all duration-300"
                                                                        style={{ width: requestWidth }}
                                                                    />
                                                                </div>
                                                            </div>
                                                        )
                                                    })}
                                                </div>
                                            )}
                                        </article>

                                        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-4">
                                            <h3 className="text-base font-semibold text-gray-900">Readiness Checks</h3>
                                            {readyPayload ? (
                                                <div className="mt-4 space-y-3">
                                                    <p className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${statusBadgeClass(readyPayload.status)}`}>
                                                        {readyPayload.status}
                                                    </p>
                                                    <p className="text-sm text-gray-500">
                                                        Timestamp: {formatTimestamp(readyPayload.timestamp)}
                                                    </p>
                                                    <ul className="space-y-2">
                                                        {readyPayload.checks.map((check) => (
                                                            <li
                                                                key={check.name}
                                                                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
                                                            >
                                                                <div className="flex items-center justify-between text-sm">
                                                                    <span className="font-semibold text-gray-900">{check.name}</span>
                                                                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(check.status)}`}>
                                                                        {check.status}
                                                                    </span>
                                                                </div>
                                                                <p className="mt-1 text-xs text-gray-500">
                                                                    latency {check.latency_ms} ms
                                                                    {check.message ? ` - ${check.message}` : ''}
                                                                </p>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            ) : (
                                                <p className="mt-3 text-sm text-gray-600">
                                                    Readiness data is available only for monitoring-enabled accounts.
                                                </p>
                                            )}
                                        </article>
                                    </section>

                                    <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md">
                                        <h3 className="text-base font-semibold text-gray-900">Auth Events</h3>
                                        {eventRows.length === 0 ? (
                                            <p className="mt-3 text-sm text-gray-600">No auth event metrics available yet.</p>
                                        ) : (
                                            <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                                                {eventRows.slice(0, 8).map((eventRow) => {
                                                    const eventWidth = `${Math.max(
                                                        8,
                                                        Math.round((eventRow.count / maxEventCount) * 100)
                                                    )}%`

                                                    return (
                                                        <div
                                                            key={`${eventRow.eventName}:${eventRow.outcome}`}
                                                            className="rounded-xl border border-gray-200 bg-gray-50 p-3"
                                                        >
                                                            <div className="flex items-center justify-between text-sm">
                                                                <div>
                                                                    <p className="font-semibold text-gray-900">{eventRow.eventName}</p>
                                                                    <p className="text-xs text-gray-500">Outcome: {eventRow.outcome}</p>
                                                                </div>
                                                                <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
                                                                    {eventRow.count}
                                                                </span>
                                                            </div>
                                                            <div className="mt-3 h-2 rounded-full bg-gray-200">
                                                                <div
                                                                    className="h-2 rounded-full bg-red-700 transition-all duration-300"
                                                                    style={{ width: eventWidth }}
                                                                />
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </article>
                                </section>
                            ) : null}
                        </>
                    ) : null}
                </div>
            </main>
        </div>
    )
}
