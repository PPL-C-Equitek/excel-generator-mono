import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MonitoringDashboardViewModel } from '../../../src/app/monitoring/useMonitoringDashboardModel'
import MonitoringPage from '../../../src/app/monitoring/MonitoringPage'

const mockUseMonitoringDashboardModel = vi.fn()

vi.mock('../../../src/components/Sidebar', () => ({
    default: () => <div data-testid="sidebar" />,
}))

vi.mock('../../../src/app/monitoring/useMonitoringDashboardModel', () => ({
    useMonitoringDashboardModel: () => mockUseMonitoringDashboardModel(),
}))

vi.mock('../../../src/app/monitoring/components/MonitoringDashboardSections', () => ({
    MonitoringHeroSection: () => <div data-testid="hero-section" />,
    MonitoringTrafficSummarySection: () => <div data-testid="summary-section" />,
    MonitoringAccessRequiredSection: () => <div data-testid="access-required" />,
    MonitoringLatencyAndMetersSection: () => <div data-testid="latency-section" />,
    MonitoringRoutesAndReadinessSection: () => <div data-testid="routes-section" />,
    MonitoringAuthEventsSection: () => <div data-testid="events-section" />,
    MonitoringTrafficSummarySkeleton: () => <div data-testid="summary-skeleton" />,
    MonitoringPanelsSkeleton: () => <div data-testid="panels-skeleton" />,
    MonitoringRoutesAndReadinessSkeleton: () => <div data-testid="routes-skeleton" />,
    MonitoringAuthEventsSkeleton: () => <div data-testid="events-skeleton" />,
}))

function buildViewModel(overrides: Partial<MonitoringDashboardViewModel> = {}): MonitoringDashboardViewModel {
    return {
        livePayload: { status: 'ok', timestamp: '2026-04-24T10:00:00Z' },
        accessDecision: { allowed: true, reason: 'ok' },
        readyPayload: null,
        statsPayload: {
            status: 'ok',
            generated_at: '2026-04-24T10:00:02Z',
            totals: { requests: 1, errors: 0, error_rate: 0 },
            routes: [],
            events: {},
        },
        isLoading: false,
        isRefreshing: false,
        errorMessage: null,
        consecutiveFailures: 0,
        retryInSeconds: 0,
        nextRetryAtMs: null,
        isDataStale: false,
        lastSync: '',
        hasRealtimeSeries: false,
        realtimeWindowSeconds: 0,
        realtimeBucketSeconds: 0,
        realtimeTotals: null,
        eventRows: [],
        maxEventCount: 1,
        maxRouteRequests: 1,
        latencySeries: [],
        latencyChart: { linePoints: '', areaPath: '', maxLatency: 0 },
        errorRateMeter: { percentText: '0.00%', progressLength: 0, colorClass: 'text-blue-600' },
        readinessMeter: {
            percentText: '--',
            progressLength: 0,
            colorClass: 'text-gray-600',
            healthyChecks: 0,
            totalChecks: 0,
        },
        refreshDashboard: vi.fn(),
        ...overrides,
    }
}

describe('MonitoringPage state announcements and branch rendering', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('announces loading state and renders section skeletons', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                isLoading: true,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Loading monitoring dashboard.')).toBeInTheDocument()
        expect(screen.getByTestId('summary-skeleton')).toBeInTheDocument()
        expect(screen.getByTestId('panels-skeleton')).toBeInTheDocument()
    })

    it('announces refreshing state', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                isRefreshing: true,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Refreshing monitoring metrics.')).toBeInTheDocument()
    })

    it('announces retrying state and triggers Retry Now action', () => {
        const refreshDashboard = vi.fn()
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                errorMessage: 'temporary issue',
                retryInSeconds: 5,
                consecutiveFailures: 2,
                refreshDashboard,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Monitoring refresh failed. Retrying in 5 seconds.')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Retry Now' }))
        expect(refreshDashboard).toHaveBeenCalledTimes(1)
    })

    it('announces failed refresh message when retry is not scheduled', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                errorMessage: 'request failed',
                retryInSeconds: 0,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Monitoring refresh failed. request failed')).toBeInTheDocument()
    })

    it('announces stale data and access-required branch when monitoring access is denied', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                isDataStale: true,
                accessDecision: { allowed: false, reason: 'no_account' },
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Monitoring data is stale.')).toBeInTheDocument()
        expect(screen.getByTestId('access-required')).toBeInTheDocument()
    })

    it('announces the last sync when data is fresh and skips details when stats is missing', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                lastSync: '2026-04-24T10:10:00Z',
                statsPayload: null,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Monitoring data updated at 2026-04-24T10:10:00Z.')).toBeInTheDocument()
        expect(screen.queryByTestId('latency-section')).not.toBeInTheDocument()
        expect(screen.queryByTestId('routes-section')).not.toBeInTheDocument()
        expect(screen.queryByTestId('events-section')).not.toBeInTheDocument()
    })

    it('announces generic dashboard ready state when no other status applies', () => {
        mockUseMonitoringDashboardModel.mockReturnValue(
            buildViewModel({
                livePayload: null,
                accessDecision: null,
            })
        )

        render(<MonitoringPage />)

        expect(screen.getByText('Monitoring dashboard ready.')).toBeInTheDocument()
    })
})
