import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MonitoringRoleGuard from '@/components/MonitoringRoleGuard'

type MonitoringAccessDecision = {
    allowed: boolean
    reason: string
}

const { mockReplace, mockRouter, mockGetMonitoringAccess } = vi.hoisted(() => {
    const replace = vi.fn()
    return {
        mockReplace: replace,
        mockRouter: {
            replace,
        },
        mockGetMonitoringAccess: vi.fn(),
    }
})

vi.mock('next/navigation', () => ({
    useRouter: () => mockRouter,
}))

vi.mock('@/services/monitoring', () => ({
    getMonitoringAccess: () => mockGetMonitoringAccess(),
}))

describe('MonitoringRoleGuard', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockGetMonitoringAccess.mockResolvedValue({
            allowed: true,
            reason: 'ok',
        })
    })

    it('renders children when monitoring access is allowed', async () => {
        render(
            <MonitoringRoleGuard>
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        await waitFor(() => {
            expect(screen.getByTestId('monitoring-content')).toBeInTheDocument()
        })

        expect(mockReplace).not.toHaveBeenCalled()
        expect(mockGetMonitoringAccess).toHaveBeenCalledTimes(1)
    })

    it('redirects to /convert and hides children when monitoring access is denied', async () => {
        mockGetMonitoringAccess.mockResolvedValue({
            allowed: false,
            reason: 'no_account',
        })

        render(
            <MonitoringRoleGuard>
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/convert')
        })

        expect(screen.queryByTestId('monitoring-content')).not.toBeInTheDocument()
        expect(mockGetMonitoringAccess).toHaveBeenCalledTimes(1)
    })

    it('redirects to /convert when the monitoring access check fails', async () => {
        mockGetMonitoringAccess.mockRejectedValue(new Error('network down'))

        render(
            <MonitoringRoleGuard>
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/convert')
        })

        expect(screen.queryByTestId('monitoring-content')).not.toBeInTheDocument()
        expect(mockGetMonitoringAccess).toHaveBeenCalledTimes(1)
    })

    it('keeps children hidden while monitoring access is pending', () => {
        mockGetMonitoringAccess.mockReturnValue(new Promise(() => undefined))

        render(
            <MonitoringRoleGuard loadingFallback={<div data-testid="loading">Checking monitoring access</div>}>
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        expect(screen.getByTestId('loading')).toBeInTheDocument()
        expect(screen.queryByTestId('monitoring-content')).not.toBeInTheDocument()
        expect(mockReplace).not.toHaveBeenCalled()
    })

    it('supports custom redirect and loading fallback', async () => {
        let resolveAccess: ((value: MonitoringAccessDecision) => void) | undefined
        mockGetMonitoringAccess.mockReturnValue(
            new Promise((resolve) => {
                resolveAccess = resolve
            })
        )

        render(
            <MonitoringRoleGuard
                redirectTo="/custom-convert"
                loadingFallback={<div data-testid="loading">Checking monitoring access</div>}
            >
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        expect(screen.getByTestId('loading')).toBeInTheDocument()

        resolveAccess?.({
            allowed: false,
            reason: 'inactive',
        })

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/custom-convert')
        })
    })

    it('does not redirect after unmount when the access check resolves late', async () => {
        let resolveAccess: ((value: MonitoringAccessDecision) => void) | undefined
        mockGetMonitoringAccess.mockReturnValue(
            new Promise((resolve) => {
                resolveAccess = resolve
            })
        )

        const { unmount } = render(
            <MonitoringRoleGuard>
                <div data-testid="monitoring-content">Monitoring Content</div>
            </MonitoringRoleGuard>
        )

        unmount()
        resolveAccess?.({
            allowed: false,
            reason: 'no_account',
        })
        await Promise.resolve()

        expect(mockReplace).not.toHaveBeenCalled()
    })
})
