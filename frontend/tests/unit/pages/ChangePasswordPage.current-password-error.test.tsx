import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const mockReplace = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace: mockReplace,
    }),
}))

vi.mock('@/components/Sidebar', () => ({
    default: ({ activeMenu }: { activeMenu: string }) => (
        <aside data-testid="sidebar">{activeMenu}</aside>
    ),
}))

vi.mock('@/lib/api', () => ({
    changePassword: vi.fn(),
}))

vi.mock('@/lib/auth', () => ({
    getValidAccessToken: vi.fn(),
    getStoredRefreshToken: vi.fn(),
    clearAuthTokens: vi.fn(),
}))

vi.mock('@/app/change-password/form', () => ({
    EMPTY_CHANGE_PASSWORD_ERRORS: {
        currentPassword: '',
        newPassword: '',
        newPasswordConfirm: '',
        form: '',
    },
    validateChangePasswordForm: vi.fn(() => ({
        isValid: false,
        errors: {
            currentPassword: 'Current password is required.',
            newPassword: '',
            newPasswordConfirm: '',
            form: '',
        },
    })),
    buildChangePasswordPayload: vi.fn(),
}))

import ChangePasswordPage from '@/app/change-password/ChangePasswordPage'

describe('ChangePasswordPage current password error rendering', () => {
    it('shows the current password field error when validation returns one', async () => {
        render(<ChangePasswordPage />)

        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        expect(
            await screen.findByText('Current password is required.')
        ).toBeInTheDocument()
    })
})
