import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MonitoringReadyPayload, MonitoringStatsPayload } from '../../../src/services/monitoring'
import type { LatencySeriesPoint } from '../../../src/app/monitoring/monitoringViewModelTypes'
import {
    MonitoringAccessRequiredSection,
    MonitoringAuthEventsSection,
    MonitoringHeroSection,
    MonitoringReadinessAlertSection,
    MonitoringLatencyAndMetersSection,
    MonitoringRoutesAndReadinessSection,
    MonitoringTrafficSummarySection,
} from '../../../src/app/monitoring/components/MonitoringDashboardSections'

const baseStatsPayload: MonitoringStatsPayload = {
    status: 'ok',
    generated_at: '2026-04-24T10:00:00Z',
    totals: {
        requests: 120,
        errors: 6,
        error_rate: 0.05,
    },
    routes: [
        {
            route: '/history/',
            method: 'GET',
            total_requests: 60,
            total_errors: 3,
            error_rate: 0.05,
            avg_latency_ms: 42,
            max_latency_ms: 90,
        },
    ],
    events: {
        'auth.login': {
            success: 12,
        },
    },
}

const baseReadyPayload: MonitoringReadyPayload = {
    status: 'ok',
    timestamp: '2026-04-24T10:00:05Z',
    checks: [
        {
            name: 'database',
            status: 'ok',
            latency_ms: 5,
            is_critical: true,
            message: 'healthy',
        },
    ],
}

describe('MonitoringDashboardSections', () => {
    it('renders hero stale badge, retry text, and refresh callback', () => {
        const onRefresh = vi.fn()

        const { rerender } = render(
            <MonitoringHeroSection
                lastSync="2026-04-24T10:00:00Z"
                isLoading={false}
                isRefreshing={true}
                isDataStale={true}
                retryInSeconds={7}
                onRefresh={onRefresh}
            />
        )

        expect(screen.getByText('Stale Data')).toBeInTheDocument()
        expect(screen.getByText('Retry in 7s')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Refreshing...' })).toBeDisabled()

        rerender(
            <MonitoringHeroSection
                lastSync="2026-04-24T10:00:00Z"
                isLoading={false}
                isRefreshing={false}
                isDataStale={false}
                retryInSeconds={0}
                onRefresh={onRefresh}
            />
        )

        fireEvent.click(screen.getByRole('button', { name: 'Refresh Monitoring' }))
        expect(screen.getByText('Live')).toBeInTheDocument()
        expect(onRefresh).toHaveBeenCalledTimes(1)
    })

    it('renders traffic summary with realtime subtitle and realtime totals', () => {
        render(
            <MonitoringTrafficSummarySection
                livePayload={{ status: 'ok', timestamp: '2026-04-24T10:00:00Z' }}
                accessDecision={{ allowed: false, reason: 'no_account' }}
                statsPayload={baseStatsPayload}
                realtimeTotals={{ requests: 40, errors: 2, errorRate: 0.05 }}
                hasRealtimeSeries={true}
                realtimeWindowSeconds={60}
            />
        )

        expect(screen.getByText(/^Generated:/)).toBeInTheDocument()
        expect(screen.getByText('Last 60s window')).toBeInTheDocument()
        expect(screen.getByText('Error rate: 5.00%')).toBeInTheDocument()
    })

    it('renders access required section with reason mapping', () => {
        render(<MonitoringAccessRequiredSection reason="no_account" />)

        expect(screen.getByText('Monitoring Access Required')).toBeInTheDocument()
        expect(screen.getByText('Monitoring account access is required for this page.')).toBeInTheDocument()
    })

    it('renders readiness alert for degraded status with critical checks', () => {
        render(
            <MonitoringReadinessAlertSection
                readyPayload={{
                    status: 'degraded',
                    timestamp: '2026-04-24T10:00:05Z',
                    checks: [
                        {
                            name: 'database',
                            status: 'ok',
                            latency_ms: 3,
                            is_critical: true,
                        },
                        {
                            name: 'queue',
                            status: 'error',
                            latency_ms: 55,
                            is_critical: true,
                            message: 'queue backlog too high',
                        },
                        {
                            name: 'filesystem',
                            status: 'warning',
                            latency_ms: 12,
                            is_critical: true,
                        },
                    ],
                }}
            />
        )

        expect(screen.getByText('Readiness Degraded')).toBeInTheDocument()
        expect(screen.getByText(/queue/i)).toBeInTheDocument()
        expect(screen.getByText(/filesystem/i)).toBeInTheDocument()
        expect(screen.getByText(/queue backlog too high/i)).toBeInTheDocument()
    })

    it('renders latency section empty state', () => {
        render(
            <MonitoringLatencyAndMetersSection
                latencySeries={[]}
                latencyChart={{ linePoints: '', areaPath: '', maxLatency: 0 }}
                hasRealtimeSeries={false}
                realtimeWindowSeconds={0}
                realtimeBucketSeconds={0}
                errorRateMeter={{ percentText: '0.00%', progressLength: 0, colorClass: 'text-blue-600' }}
                readinessMeter={{
                    percentText: '--',
                    progressLength: 0,
                    colorClass: 'text-gray-600',
                    healthyChecks: 0,
                    totalChecks: 0,
                }}
            />
        )

        expect(screen.getByText('No latency data available yet.')).toBeInTheDocument()
        expect(screen.getByText('Target < 5%')).toBeInTheDocument()
    })

    it('renders latency realtime chart details and latest bucket', () => {
        const latencySeries: LatencySeriesPoint[] = [
            { id: 1, label: '10:00:00', value: 30, requests: 2 },
            { id: 2, label: '10:00:10', value: 45, requests: 3 },
            { id: 3, label: '10:00:20', value: 40, requests: 2 },
            { id: 4, label: '10:00:30', value: 25, requests: 4 },
            { id: 5, label: '10:00:40', value: 50, requests: 6 },
            { id: 6, label: '10:00:50', value: 42, requests: 5 },
            {
                id: 7,
                label: '10:01:00',
                value: 47,
            } as unknown as LatencySeriesPoint,
        ]

        render(
            <MonitoringLatencyAndMetersSection
                latencySeries={latencySeries}
                latencyChart={{
                    linePoints: '26,120 80,100 130,110',
                    areaPath: 'M 26 190 L 26 120 L 80 100 L 130 110 L 130 190 Z',
                    maxLatency: 50,
                }}
                hasRealtimeSeries={true}
                realtimeWindowSeconds={60}
                realtimeBucketSeconds={10}
                errorRateMeter={{ percentText: '5.00%', progressLength: 12.56, colorClass: 'text-blue-600' }}
                readinessMeter={{
                    percentText: '100%',
                    progressLength: 251.2,
                    colorClass: 'text-blue-600',
                    healthyChecks: 3,
                    totalChecks: 3,
                }}
            />
        )

        expect(screen.getByText('Realtime 10s Buckets')).toBeInTheDocument()
        expect(screen.getByText('Peak latency in last 60s:')).toBeInTheDocument()
        const latestBucketSummary = screen.getByText(/Latest bucket/).closest('div')
        expect(latestBucketSummary).toHaveTextContent('across 0 requests.')
        expect(screen.getByText('Window 60s')).toBeInTheDocument()
        expect(screen.getByText('Latency trend line chart')).toBeInTheDocument()
    })

    it('shows even-index and trailing labels only for longer latency series', () => {
        const longLatencySeries: LatencySeriesPoint[] = [
            { id: 1, label: '10:00:00', value: 30, requests: 1 },
            { id: 2, label: '10:00:10', value: 40, requests: 2 },
            { id: 3, label: '10:00:20', value: 35, requests: 3 },
            { id: 4, label: '10:00:30', value: 50, requests: 4 },
            { id: 5, label: '10:00:40', value: 45, requests: 5 },
            { id: 6, label: '10:00:50', value: 60, requests: 6 },
            { id: 7, label: '10:01:00', value: 55, requests: 7 },
        ]

        render(
            <MonitoringLatencyAndMetersSection
                latencySeries={longLatencySeries}
                latencyChart={{
                    linePoints: '',
                    areaPath: '',
                    maxLatency: 60,
                }}
                hasRealtimeSeries={true}
                realtimeWindowSeconds={60}
                realtimeBucketSeconds={10}
                errorRateMeter={{ percentText: '10.00%', progressLength: 25.12, valueClassName: 'text-blue-600' }}
                readinessMeter={{
                    percentText: '100%',
                    progressLength: 251.2,
                    valueClassName: 'text-blue-600',
                    healthyChecks: 1,
                    totalChecks: 1,
                }}
            />
        )

        expect(screen.getByText('10:00:00')).toBeInTheDocument()
        expect(screen.queryByText('10:00:10')).toBeNull()
        expect(screen.getByText('10:01:00')).toBeInTheDocument()
    })

    it('renders latency snapshot fallback labels when realtime is unavailable', () => {
        render(
            <MonitoringLatencyAndMetersSection
                latencySeries={[
                    { id: 1, label: '/history/', value: 40, requests: 4 },
                    { id: 2, label: '/auth/login/', value: 50, requests: 2 },
                ]}
                latencyChart={{
                    linePoints: '',
                    areaPath: '',
                    maxLatency: 50,
                }}
                hasRealtimeSeries={false}
                realtimeWindowSeconds={0}
                realtimeBucketSeconds={0}
                errorRateMeter={{ percentText: '2.00%', progressLength: 5.02, colorClass: 'text-blue-600' }}
                readinessMeter={{
                    percentText: '50%',
                    progressLength: 125.6,
                    colorClass: 'text-red-700',
                    healthyChecks: 1,
                    totalChecks: 2,
                }}
            />
        )

        expect(screen.getByText('Avg Route Latency')).toBeInTheDocument()
        expect(screen.getByText('Peak observed latency in this snapshot:')).toBeInTheDocument()
        expect(screen.getByText('[1]')).toBeInTheDocument()
    })

    it('renders routes empty state and readiness fallback', () => {
        render(
            <MonitoringRoutesAndReadinessSection
                statsPayload={{ ...baseStatsPayload, routes: [] }}
                maxRouteRequests={1}
                readyPayload={null}
            />
        )

        expect(screen.getByText('No route metrics available yet.')).toBeInTheDocument()
        expect(screen.getByText('Readiness data is available only for monitoring-enabled accounts.')).toBeInTheDocument()
    })

    it('renders readiness checks with optional check messages', () => {
        render(
            <MonitoringRoutesAndReadinessSection
                statsPayload={baseStatsPayload}
                maxRouteRequests={60}
                readyPayload={baseReadyPayload}
            />
        )

        expect(screen.getByText(/^Timestamp:/)).toBeInTheDocument()
        expect(screen.getByText('latency 5 ms - healthy')).toBeInTheDocument()
    })

    it('renders auth events empty state', () => {
        render(<MonitoringAuthEventsSection eventRows={[]} maxEventCount={1} />)

        expect(screen.getByText('No auth event metrics available yet.')).toBeInTheDocument()
    })
})
