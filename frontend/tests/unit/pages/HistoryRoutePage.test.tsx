import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Page from '../../../src/app/history/page'

vi.mock('../../../src/components/AuthGuard', () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="auth-guard">{children}</div>
    ),
}))

vi.mock('../../../src/app/history/HistoryPage', () => ({
    default: () => <div data-testid="history-page">History Page</div>,
}))

describe('history route page', () => {
    it('wraps the history page with AuthGuard', () => {
        render(<Page />)

        expect(screen.getByTestId('auth-guard')).toBeInTheDocument()
        expect(screen.getByTestId('history-page')).toBeInTheDocument()
    })
})
