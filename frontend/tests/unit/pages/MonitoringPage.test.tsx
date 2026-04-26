import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MonitoringPage from '../../../src/app/monitoring/MonitoringPage'
vi.mock('@/lib/auth', () => ({
    getValidAccessToken: vi.fn().mockResolvedValue('page-access-token'),
}))

vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu }: { activeMenu: string }) => (
        <div data-testid="sidebar">
            <div data-testid="active-menu">{activeMenu}</div>
        </div>
    ),
}))

type MockMonitoringService = {
    getMonitoringLive: ReturnType<typeof vi.fn>
    getMonitoringAccess: ReturnType<typeof vi.fn>
    getMonitoringReady: ReturnType<typeof vi.fn>
    getMonitoringStats: ReturnType<typeof vi.fn>
}

function makeService(overrides?: Partial<MockMonitoringService>): MockMonitoringService {
    return {
        getMonitoringLive: vi.fn().mockResolvedValue({
            status: 'ok',
            timestamp: '2026-04-24T10:00:00Z',
        }),
        getMonitoringAccess: vi.fn().mockResolvedValue({
            allowed: true,
            reason: 'ok',
        }),
        getMonitoringReady: vi.fn().mockResolvedValue({
            status: 'ok',
            timestamp: '2026-04-24T10:00:01Z',
            checks: [
                { name: 'database', status: 'ok', latency_ms: 2, is_critical: true },
            ],
        }),
        getMonitoringStats: vi.fn().mockResolvedValue({
            status: 'ok',
            generated_at: '2026-04-24T10:00:02Z',
            totals: { requests: 25, errors: 1, error_rate: 0.04 },
            routes: [
                {
                    route: 'auth/login/',
                    method: 'POST',
                    total_requests: 20,
                    total_errors: 1,
                    error_rate: 0.05,
                    avg_latency_ms: 21.5,
                    max_latency_ms: 40,
                },
            ],
            events: {
                'auth.login': {
                    success: 10,
                    client_error: 2,
                },
            },
        }),
        ...overrides,
    }
}

describe('MonitoringPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders dashboard data for a monitoring-enabled user', async () => {
        const service = makeService()

        render(<MonitoringPage monitoringService={service} />)

        expect(screen.getByTestId('active-menu')).toHaveTextContent('monitoring')

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)
            expect(service.getMonitoringAccess).toHaveBeenCalledTimes(1)
            expect(service.getMonitoringReady).toHaveBeenCalledTimes(1)
            expect(service.getMonitoringStats).toHaveBeenCalledTimes(1)
        })

        expect(screen.getByText('System Monitoring')).toBeInTheDocument()
        expect(screen.getByText('Traffic Summary')).toBeInTheDocument()
        expect(screen.getByText('Top Routes')).toBeInTheDocument()
        expect(screen.getByText('Auth Events')).toBeInTheDocument()
    })

    it('shows access warning and skips ready/stats when user is not monitoring-enabled', async () => {
        const service = makeService({
            getMonitoringAccess: vi.fn().mockResolvedValue({
                allowed: false,
                reason: 'no_account',
            }),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
        })

        render(<MonitoringPage monitoringService={service} />)

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)
            expect(service.getMonitoringAccess).toHaveBeenCalledTimes(1)
        })

        expect(
            screen.getAllByText('Monitoring account access is required for this page.').length
        ).toBeGreaterThan(0)
        expect(service.getMonitoringReady).not.toHaveBeenCalled()
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
    })

    it('refreshes dashboard data when refresh button is clicked', async () => {
        const service = makeService()

        render(<MonitoringPage monitoringService={service} />)

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)
        })

        fireEvent.click(screen.getByRole('button', { name: 'Refresh Monitoring' }))

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalledTimes(2)
            expect(service.getMonitoringAccess).toHaveBeenCalledTimes(2)
        })
    })
})
