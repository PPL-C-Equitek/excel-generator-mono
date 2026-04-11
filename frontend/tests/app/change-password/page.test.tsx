import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Page from '@/app/change-password/page'

vi.mock('@/components/AuthGuard', () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="auth-guard">{children}</div>
    ),
}))

vi.mock('@/app/change-password/ChangePasswordPage', () => ({
    default: () => <div data-testid="change-password-page">Change Password Page</div>,
}))

describe('change-password/page', () => {
    it('wraps the page with AuthGuard', () => {
        render(<Page />)

        expect(screen.getByTestId('auth-guard')).toBeInTheDocument()
        expect(screen.getByTestId('change-password-page')).toBeInTheDocument()
    })
})
