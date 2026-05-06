import { useId } from 'react'
import type {
    MonitoringAccessDecision,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
} from '@/services/monitoring'
import {
    formatPercent,
    formatReadinessCheckName,
    formatStatusLabel,
    formatTimestamp,
    resolveAccessMessage,
} from '../monitoringUi'
import type {
    ErrorRateMeter,
    EventRow,
    LatencyChartModel,
    LatencySeriesPoint,
    ReadinessMeter,
    RealtimeTotals,
} from '../monitoringViewModelTypes'
import { monitoringRouteVisibilityPolicy } from '../monitoringRoutePolicy'
import { GaugeMeter, MetricCard, StatusBadge } from './primitives/MonitoringPrimitives'

type MonitoringHeroSectionProps = Readonly<{
    lastSync: string
    isLoading: boolean
    isRefreshing: boolean
    isDataStale: boolean
    retryInSeconds: number
    onRefresh: () => void
}>

export function MonitoringHeroSection({
    lastSync,
    isLoading,
    isRefreshing,
    isDataStale,
    retryInSeconds,
    onRefresh,
}: MonitoringHeroSectionProps) {
    return (
        <section className="rounded-2xl border border-gray-700/40 bg-gradient-to-br from-gray-950 via-gray-900 to-gray-800 p-6 shadow-xl">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="space-y-3">
                    <span className="inline-flex rounded-full border border-red-300/30 bg-red-700/20 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-red-200">
                        Monitoring
                    </span>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight text-white">System Monitoring</h1>
                        <p className="mt-2 max-w-2xl text-sm text-gray-300">
                            Live health, readiness, traffic, and auth activity for your backend.
                        </p>
                    </div>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-gray-200">
                        Last sync: <span className="font-semibold text-white">{lastSync ? formatTimestamp(lastSync) : '--'}</span>
                        <div className="mt-2 flex items-center gap-2">
                            {isDataStale ? (
                                <span className="inline-flex rounded-full border border-red-300/40 bg-red-700/20 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-red-200">
                                    Stale Data
                                </span>
                            ) : null}
                            {retryInSeconds > 0 ? (
                                <span className="text-xs text-gray-300">Retry in {retryInSeconds}s</span>
                            ) : null}
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onRefresh}
                        disabled={isLoading || isRefreshing}
                        className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-all duration-150 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isRefreshing ? 'Refreshing...' : 'Refresh Monitoring'}
                    </button>
                </div>
            </div>
        </section>
    )
}

type MonitoringTrafficSummarySectionProps = Readonly<{
    livePayload: MonitoringLivePayload
    accessDecision: MonitoringAccessDecision
    statsPayload: MonitoringStatsPayload | null
    realtimeTotals: RealtimeTotals
    hasRealtimeSeries: boolean
    realtimeWindowSeconds: number
}>

export function MonitoringTrafficSummarySection({
    livePayload,
    accessDecision,
    statsPayload,
    realtimeTotals,
    hasRealtimeSeries,
    realtimeWindowSeconds,
}: MonitoringTrafficSummarySectionProps) {
    return (
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
                <MetricCard
                    title="Live Status"
                    value={<StatusBadge status={livePayload.status} label={formatStatusLabel(livePayload.status)} />}
                    valueClassName="text-base"
                    subtitle={formatTimestamp(livePayload.timestamp)}
                />

                <MetricCard
                    title="Access"
                    value={<StatusBadge status={accessDecision.allowed ? 'success' : 'error'} label={accessDecision.allowed ? 'Allowed' : 'Denied'} />}
                    valueClassName="text-base"
                    subtitle={resolveAccessMessage(accessDecision.reason)}
                />

                <MetricCard
                    title="Total Requests"
                    value={statsPayload ? (realtimeTotals?.requests ?? statsPayload.totals.requests) : '--'}
                    subtitle={
                        hasRealtimeSeries && realtimeWindowSeconds > 0
                            ? `Last ${realtimeWindowSeconds}s window`
                            : 'Backend traffic volume'
                    }
                />

                <MetricCard
                    title="Errors"
                    value={statsPayload ? (realtimeTotals?.errors ?? statsPayload.totals.errors) : '--'}
                    valueClassName="text-red-700"
                    subtitle={
                        statsPayload
                            ? `Error rate: ${formatPercent(realtimeTotals?.errorRate ?? statsPayload.totals.error_rate)}`
                            : '--'
                    }
                />
            </div>
        </section>
    )
}

type MonitoringAccessRequiredSectionProps = Readonly<{
    reason: string
}>

export function MonitoringAccessRequiredSection({ reason }: MonitoringAccessRequiredSectionProps) {
    return (
        <section className="rounded-2xl border border-red-300 bg-red-50 p-5 shadow-md">
            <h3 className="text-base font-semibold text-red-700">Monitoring Access Required</h3>
            <p className="mt-2 text-sm text-red-700">{resolveAccessMessage(reason)}</p>
        </section>
    )
}

type MonitoringReadinessAlertSectionProps = Readonly<{
    readyPayload: MonitoringReadyPayload | null
}>

export function MonitoringReadinessAlertSection({
    readyPayload,
}: MonitoringReadinessAlertSectionProps) {
    if (!readyPayload) {
        return null
    }

    const status = readyPayload.status.toLowerCase()
    const isHealthy = status === 'ok' || status === 'healthy'
    if (isHealthy) {
        return null
    }

    const degradedChecks = readyPayload.checks.filter((check) => check.status.toLowerCase() !== 'ok')

    return (
        <section className="rounded-2xl border border-amber-300 bg-amber-50 p-5 shadow-md">
            <h3 className="text-base font-semibold text-amber-800">Readiness Degraded</h3>
            <p className="mt-1 text-sm text-amber-700">
                Monitoring readiness is not fully green.
            </p>
            <ul className="mt-3 space-y-2 text-sm text-amber-800">
                {degradedChecks.length === 0 ? (
                    <li>Overall readiness is in degraded state.</li>
                ) : (
                    degradedChecks.map((check) => (
                        <li
                            key={`${check.name}:${check.status}`}
                            className="rounded-lg border border-amber-200 bg-amber-100/50 px-3 py-2"
                        >
                            <span className="font-semibold">{formatReadinessCheckName(check.name)}</span>: {formatStatusLabel(check.status)}
                            {check.message ? <span className="text-amber-900"> - {check.message}</span> : null}
                        </li>
                    ))
                )}
            </ul>
        </section>
    )
}

type MonitoringLatencyAndMetersSectionProps = Readonly<{
    latencySeries: LatencySeriesPoint[]
    latencyChart: LatencyChartModel
    hasRealtimeSeries: boolean
    realtimeWindowSeconds: number
    realtimeBucketSeconds: number
    errorRateMeter: ErrorRateMeter
    readinessMeter: ReadinessMeter
}>

type LatencyChartPanelProps = Readonly<{
    latencySeries: LatencySeriesPoint[]
    latencyChart: LatencyChartModel
    hasRealtimeSeries: boolean
    realtimeWindowSeconds: number
    realtimeBucketSeconds: number
}>

function formatLatencyAxisLabel(value: number): string {
    return value < 10 ? `${value.toFixed(1)}ms` : `${value.toFixed(0)}ms`
}

function resolveLatencyChartDescription(
    hasRealtimeSeries: boolean,
    realtimeWindowSeconds: number,
    realtimeBucketSeconds: number,
): string {
    if (!hasRealtimeSeries || realtimeWindowSeconds <= 0) {
        return 'Latency trend for the top monitored routes from the latest snapshot.'
    }

    return `Latency trend over ${realtimeWindowSeconds} seconds, grouped every ${realtimeBucketSeconds} seconds.`
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

function LatencyChartPanel({
    latencySeries,
    latencyChart,
    hasRealtimeSeries,
    realtimeWindowSeconds,
    realtimeBucketSeconds,
}: LatencyChartPanelProps) {
    const lineChartTitleId = useId()
    const lineChartDescId = useId()
    const lineChartDescription = resolveLatencyChartDescription(
        hasRealtimeSeries,
        realtimeWindowSeconds,
        realtimeBucketSeconds,
    )
    const latestLatencyPoint = latencySeries.at(-1)
    const maxRequestsInSeries = Math.max(0, ...latencySeries.map((entry) => entry.requests ?? 0))
    const yAxisTopMs = Math.max(1, latencyChart.maxLatency)
    const yAxisMidMs = yAxisTopMs / 2
    const yAxisTopLabel = formatLatencyAxisLabel(yAxisTopMs)
    const yAxisMidLabel = formatLatencyAxisLabel(yAxisMidMs)
    const latencyModeLabel = hasRealtimeSeries ? `Realtime ${realtimeBucketSeconds}s Buckets` : 'Avg Route Latency'
    const peakLatencyContextLabel = hasRealtimeSeries && realtimeWindowSeconds > 0
        ? `Peak latency in last ${realtimeWindowSeconds}s:`
        : 'Peak observed latency in this snapshot:'

    return (
        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
            <div className="flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold text-gray-900">Latency Line Chart</h3>
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500">
                    {latencyModeLabel}
                </span>
            </div>

            {latencySeries.length === 0 ? (
                <p className="mt-4 text-sm text-gray-600">No latency data available yet.</p>
            ) : (
                <>
                    <div className="mt-4 overflow-x-auto rounded-xl border border-gray-200 bg-gray-50 p-3">
                        <p className="mb-2 text-xs text-gray-500">
                            Y-axis: Avg latency (ms). Max requests in series: {maxRequestsInSeries}
                        </p>
                        <svg
                            viewBox="0 0 520 220"
                            className="h-52 w-full min-w-[520px]"
                            aria-labelledby={`${lineChartTitleId} ${lineChartDescId}`}
                            tabIndex={0}
                        >
                            <title id={lineChartTitleId}>Latency trend line chart</title>
                            <desc id={lineChartDescId}>{lineChartDescription}</desc>
                            <line x1="26" y1="190" x2="494" y2="190" stroke="#d1d5db" strokeWidth="1" />
                            <line x1="26" y1="16" x2="26" y2="190" stroke="#d1d5db" strokeWidth="1" />
                            <text x="4" y="20" fontSize="11" fill="#6b7280">
                                {yAxisTopLabel}
                            </text>
                            <text x="4" y="104" fontSize="11" fill="#6b7280">
                                {yAxisMidLabel}
                            </text>
                            <text x="16" y="194" fontSize="11" fill="#6b7280">
                                0
                            </text>
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
                                const normalizedY = Math.min(
                                    1,
                                    Math.max(0, entry.value / Math.max(1, latencyChart.maxLatency))
                                )
                                const x = 26 + normalizedX * (520 - 52)
                                const y = 16 + (1 - normalizedY) * (220 - 46)
                                const showLabel = shouldShowLatencyPointLabel(
                                    latencySeries.length,
                                    index,
                                    entry === latestLatencyPoint,
                                )
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
                        {peakLatencyContextLabel}{' '}
                        <span className="font-semibold text-gray-900">{latencyChart.maxLatency.toFixed(2)} ms</span>
                    </p>
                    {hasRealtimeSeries ? (
                        <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                            Latest bucket {latestLatencyPoint?.label}: avg latency{' '}
                            <span className="font-semibold text-gray-900">
                                {latestLatencyPoint?.value.toFixed(2)} ms
                            </span>{' '}
                            across{' '}
                            <span className="font-semibold text-gray-900">
                                {latestLatencyPoint?.requests ?? 0}
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
    )
}

export function MonitoringLatencyAndMetersSection({
    latencySeries,
    latencyChart,
    hasRealtimeSeries,
    realtimeWindowSeconds,
    realtimeBucketSeconds,
    errorRateMeter,
    readinessMeter,
}: MonitoringLatencyAndMetersSectionProps) {
    return (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <LatencyChartPanel
                latencySeries={latencySeries}
                latencyChart={latencyChart}
                hasRealtimeSeries={hasRealtimeSeries}
                realtimeWindowSeconds={realtimeWindowSeconds}
                realtimeBucketSeconds={realtimeBucketSeconds}
            />

            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-4">
                <h3 className="text-base font-semibold text-gray-900">Meter Panels</h3>

                <div className="mt-4 grid grid-cols-1 gap-4">
                    <GaugeMeter
                        ariaLabel="Error rate meter"
                        label="Error Rate Meter"
                        valueText={errorRateMeter.percentText}
                        caption={hasRealtimeSeries && realtimeWindowSeconds > 0 ? `Window ${realtimeWindowSeconds}s` : 'Target < 5%'}
                        progressLength={errorRateMeter.progressLength}
                        strokeColor="#b91c1c"
                        valueClassName={errorRateMeter.colorClass}
                    />

                    <GaugeMeter
                        ariaLabel="Readiness meter"
                        label="Readiness Meter"
                        valueText={readinessMeter.percentText}
                        caption={`Healthy checks: ${readinessMeter.healthyChecks}/${readinessMeter.totalChecks}`}
                        progressLength={readinessMeter.progressLength}
                        strokeColor="#2563eb"
                        valueClassName={readinessMeter.colorClass}
                    />
                </div>
            </article>
        </section>
    )
}

type MonitoringRoutesAndReadinessSectionProps = Readonly<{
    statsPayload: MonitoringStatsPayload
    maxRouteRequests: number
    readyPayload: MonitoringReadyPayload | null
}>

export function MonitoringRoutesAndReadinessSection({
    statsPayload,
    maxRouteRequests,
    readyPayload,
}: MonitoringRoutesAndReadinessSectionProps) {
    const visibleRoutes = monitoringRouteVisibilityPolicy.filterVisibleRoutes(statsPayload.routes)

    return (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
                <h3 className="text-base font-semibold text-gray-900">Top Routes</h3>
                {visibleRoutes.length === 0 ? (
                    <p className="mt-3 text-sm text-gray-600">No route metrics available yet.</p>
                ) : (
                    <div className="mt-4 space-y-3">
                        {visibleRoutes.slice(0, 6).map((routeRow) => {
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
                        <StatusBadge status={readyPayload.status} label={formatStatusLabel(readyPayload.status)} />
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
                                        <span className="font-semibold text-gray-900">{formatReadinessCheckName(check.name)}</span>
                                        <StatusBadge
                                            status={check.status}
                                            label={formatStatusLabel(check.status)}
                                            className="px-2 py-0.5 text-xs"
                                        />
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
    )
}

type MonitoringAuthEventsSectionProps = Readonly<{
    eventRows: EventRow[]
    maxEventCount: number
}>

export function MonitoringAuthEventsSection({ eventRows, maxEventCount }: MonitoringAuthEventsSectionProps) {
    return (
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
    )
}

function SkeletonCard() {
    return (
        <article className="rounded-xl border border-gray-200 bg-gray-50 p-4">
            <div className="h-3 w-20 animate-pulse rounded bg-gray-200" />
            <div className="mt-4 h-8 w-24 animate-pulse rounded bg-gray-200" />
            <div className="mt-3 h-3 w-32 animate-pulse rounded bg-gray-200" />
        </article>
    )
}

export function MonitoringTrafficSummarySkeleton() {
    return (
        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md">
            <div className="mb-4 flex items-center justify-between">
                <div className="h-5 w-40 animate-pulse rounded bg-gray-200" />
                <div className="h-3 w-36 animate-pulse rounded bg-gray-200" />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
            </div>
        </section>
    )
}

export function MonitoringPanelsSkeleton() {
    return (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
                <div className="h-5 w-40 animate-pulse rounded bg-gray-200" />
                <div className="mt-4 h-52 w-full animate-pulse rounded-xl bg-gray-100" />
            </article>
            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-4">
                <div className="h-5 w-28 animate-pulse rounded bg-gray-200" />
                <div className="mt-4 h-28 w-full animate-pulse rounded-xl bg-gray-100" />
                <div className="mt-4 h-28 w-full animate-pulse rounded-xl bg-gray-100" />
            </article>
        </section>
    )
}

export function MonitoringRoutesAndReadinessSkeleton() {
    return (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-8">
                <div className="h-5 w-28 animate-pulse rounded bg-gray-200" />
                <div className="mt-4 space-y-3">
                    <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                    <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                    <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                </div>
            </article>
            <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md lg:col-span-4">
                <div className="h-5 w-32 animate-pulse rounded bg-gray-200" />
                <div className="mt-4 h-36 w-full animate-pulse rounded-xl bg-gray-100" />
            </article>
        </section>
    )
}

export function MonitoringAuthEventsSkeleton() {
    return (
        <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-md">
            <div className="h-5 w-24 animate-pulse rounded bg-gray-200" />
            <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
                <div className="h-16 w-full animate-pulse rounded-xl bg-gray-100" />
            </div>
        </article>
    )
}
