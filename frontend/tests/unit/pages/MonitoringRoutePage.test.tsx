import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import Page from '../../../src/app/monitoring/page'

vi.mock('../../../src/components/AuthGuard', () => ({
    default: ({ children }: { children: ReactNode }) => (
        <div data-testid="auth-guard">{children}</div>
    ),
}))

vi.mock('../../../src/components/MonitoringRoleGuard', () => ({
    default: ({ children }: { children: ReactNode }) => (
        <div data-testid="monitoring-role-guard">{children}</div>
    ),
}))

vi.mock('../../../src/app/monitoring/MonitoringPage', () => ({
    default: () => <div data-testid="monitoring-page" />,
}))

describe('Monitoring route page wrapper', () => {
    it('wraps MonitoringPage with AuthGuard and MonitoringRoleGuard', () => {
        render(<Page />)
        expect(screen.getByTestId('auth-guard')).toBeInTheDocument()
        expect(screen.getByTestId('monitoring-role-guard')).toBeInTheDocument()
        expect(screen.getByTestId('monitoring-page')).toBeInTheDocument()
    })
})
