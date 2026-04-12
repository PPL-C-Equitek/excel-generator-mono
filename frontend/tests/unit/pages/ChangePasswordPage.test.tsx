import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChangePasswordPage, {
    validateChangePasswordForm,
} from '@/app/change-password/ChangePasswordPage'
import { buildChangePasswordPayload } from '@/app/change-password/form'

const mockReplace = vi.fn()
const mockChangePassword = vi.fn()
const mockGetValidAccessToken = vi.fn<() => Promise<string | null>>()
const mockGetStoredRefreshToken = vi.fn<() => string | null>()
const mockClearAuthTokens = vi.fn()

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
    changePassword: (...args: unknown[]) => mockChangePassword(...args),
}))

vi.mock('@/lib/auth', () => ({
    getValidAccessToken: () => mockGetValidAccessToken(),
    getStoredRefreshToken: () => mockGetStoredRefreshToken(),
    clearAuthTokens: () => mockClearAuthTokens(),
}))

describe('validateChangePasswordForm', () => {
    it('requires a new password', () => {
        expect(
            validateChangePasswordForm({
                currentPassword: '',
                newPassword: '',
                newPasswordConfirm: '',
            })
        ).toEqual({
            isValid: false,
            errors: {
                currentPassword: '',
                newPassword: 'New password is required.',
                newPasswordConfirm: 'Password confirmation is required.',
                form: '',
            },
        })
    })

    it('rejects a weak password', () => {
        const result = validateChangePasswordForm({
            currentPassword: '',
            newPassword: 'weakpass',
            newPasswordConfirm: 'weakpass',
        })

        expect(result.isValid).toBe(false)
        expect(result.errors.newPassword).toMatch(/Password must be at least 8 characters long/i)
    })

    it('rejects a mismatched confirmation', () => {
        const result = validateChangePasswordForm({
            currentPassword: '',
            newPassword: 'Strong#123',
            newPasswordConfirm: 'Strong#124',
        })

        expect(result.isValid).toBe(false)
        expect(result.errors.newPasswordConfirm).toBe(
            'Password confirmation does not match.'
        )
    })

    it('omits refresh_token when there is no stored refresh token', () => {
        expect(
            buildChangePasswordPayload({
                currentPassword: '',
                newPassword: 'Strong#123',
                newPasswordConfirm: 'Strong#123',
                refreshToken: null,
            })
        ).toEqual({
            current_password: '',
            new_password: 'Strong#123',
            new_password_confirm: 'Strong#123',
            refresh_token: undefined,
        })
    })
})

describe('ChangePasswordPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useRealTimers()
        mockGetValidAccessToken.mockResolvedValue('access-token')
        mockGetStoredRefreshToken.mockReturnValue('refresh-token')
        mockChangePassword.mockResolvedValue({
            message: 'Password changed successfully.',
        })
    })

    it('renders the page inside the app layout', () => {
        render(<ChangePasswordPage />)

        expect(screen.getByTestId('sidebar')).toHaveTextContent('change-password')
        expect(screen.getByRole('heading', { name: /change password/i })).toBeInTheDocument()
        expect(screen.getByLabelText(/current password/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/^new password$/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument()
    })

    it('shows client validation errors and skips the API call', async () => {
        render(<ChangePasswordPage />)

        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        await waitFor(() => {
            expect(screen.getByText('New password is required.')).toBeInTheDocument()
            expect(
                screen.getByText('Password confirmation is required.')
            ).toBeInTheDocument()
        })

        expect(mockChangePassword).not.toHaveBeenCalled()
    })

    it('submits the change request, clears auth, and redirects to login', async () => {
        vi.useFakeTimers()
        render(<ChangePasswordPage />)

        fireEvent.change(screen.getByLabelText(/current password/i), {
            target: { value: 'Current#123' },
        })
        fireEvent.change(screen.getByLabelText(/^new password$/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.change(screen.getByLabelText(/confirm new password/i), {
            target: { value: 'Updated#123' },
        })

        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        await act(async () => {
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(mockChangePassword).toHaveBeenCalledWith('access-token', {
            current_password: 'Current#123',
            new_password: 'Updated#123',
            new_password_confirm: 'Updated#123',
            refresh_token: 'refresh-token',
        })

        expect(mockClearAuthTokens).toHaveBeenCalledTimes(1)
        expect(
            screen.getByText('Password changed successfully.')
        ).toBeInTheDocument()

        await act(async () => {
            vi.advanceTimersByTime(2500)
        })

        expect(mockReplace).toHaveBeenCalledWith('/login')
    })

    it('uses the fallback success message when the API returns no message', async () => {
        vi.useFakeTimers()
        mockChangePassword.mockResolvedValueOnce({})
        render(<ChangePasswordPage />)

        fireEvent.change(screen.getByLabelText(/current password/i), {
            target: { value: 'Current#123' },
        })
        fireEvent.change(screen.getByLabelText(/^new password$/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.change(screen.getByLabelText(/confirm new password/i), {
            target: { value: 'Updated#123' },
        })

        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        await act(async () => {
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(
            screen.getByText('Your password has been updated successfully.')
        ).toBeInTheDocument()

        await act(async () => {
            vi.advanceTimersByTime(2500)
        })

        expect(mockReplace).toHaveBeenCalledWith('/login')
    })

    it('redirects to login when no valid access token exists', async () => {
        mockGetValidAccessToken.mockResolvedValue(null)
        render(<ChangePasswordPage />)

        fireEvent.change(screen.getByLabelText(/^new password$/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.change(screen.getByLabelText(/confirm new password/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })
        expect(mockChangePassword).not.toHaveBeenCalled()
    })

    it('shows backend errors from the API', async () => {
        mockChangePassword.mockRejectedValueOnce(
            new Error('Current password is incorrect.')
        )
        render(<ChangePasswordPage />)

        fireEvent.change(screen.getByLabelText(/current password/i), {
            target: { value: 'Wrong#123' },
        })
        fireEvent.change(screen.getByLabelText(/^new password$/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.change(screen.getByLabelText(/confirm new password/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        expect(
            await screen.findByText('Current password is incorrect.')
        ).toBeInTheDocument()
        expect(mockClearAuthTokens).not.toHaveBeenCalled()
    })

    it('uses the fallback error when the API rejects with a non-Error value', async () => {
        mockChangePassword.mockRejectedValueOnce('unexpected')
        render(<ChangePasswordPage />)

        fireEvent.change(screen.getByLabelText(/current password/i), {
            target: { value: 'Wrong#123' },
        })
        fireEvent.change(screen.getByLabelText(/^new password$/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.change(screen.getByLabelText(/confirm new password/i), {
            target: { value: 'Updated#123' },
        })
        fireEvent.click(screen.getByRole('button', { name: /change password/i }))

        expect(
            await screen.findByText('Failed to change password.')
        ).toBeInTheDocument()
    })
})
