import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../../src/components/Navbar', () => ({
    default: () => <nav data-testid="navbar" />,
}))

vi.mock('../../../src/components/LoginForm', () => ({
    default: ({ onSubmit, onGoogleSignIn, errorMessage, successMessage, onDismissSuccess }: {
        onSubmit?: (data: { email: string; password: string }) => void
        onGoogleSignIn?: () => void
        errorMessage?: string | null
        successMessage?: string | null
        onDismissSuccess?: () => void
    }) => (
        <div>
            <button
                type="button"
                data-testid="mock-submit"
                onClick={() => onSubmit?.({ email: 'user@example.com', password: 'secret' })}
            >
                submit
            </button>
            <button
                type="button"
                onClick={() => onGoogleSignIn?.()}
            >
                Sign In with Google
            </button>
            {errorMessage && <p data-testid="mock-error">{errorMessage}</p>}
            {successMessage && <p data-testid="mock-success">{successMessage}</p>}
            <button
                type="button"
                data-testid="mock-dismiss-success"
                onClick={() => onDismissSuccess?.()}
            >
                dismiss
            </button>
        </div>
    ),
}))

vi.mock('@react-oauth/google', () => ({
    useGoogleLogin: vi.fn(() => vi.fn()),
}))

vi.mock('@/lib/api', () => ({
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
}))

import LoginPage from '../../../src/app/login/LoginPage'
import { login, loginWithGoogle } from '@/lib/api'
import { useGoogleLogin } from '@react-oauth/google'

describe('LoginPage coverage branches', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        localStorage.clear()
    })

    it('executes onDismissSuccess callback path', async () => {
        render(<LoginPage />)

        fireEvent.click(screen.getByTestId('mock-dismiss-success'))
        expect(screen.getByTestId('mock-dismiss-success')).toBeInTheDocument()
    })

    it('shows login fallback error when Error message is empty', async () => {
        vi.mocked(login).mockRejectedValue(new Error(''))

        render(<LoginPage />)

        fireEvent.click(screen.getByTestId('mock-submit'))

        await waitFor(() => {
            expect(screen.getByText('Login failed. Please try again.')).toBeInTheDocument()
        })
    })

    it('shows Google fallback error when Error message is empty', async () => {
        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'mock-client-id'

        vi.mocked(useGoogleLogin).mockImplementation((options) => {
            return () => options.onSuccess?.({ access_token: 'google-token' } as never)
        })
        vi.mocked(loginWithGoogle).mockRejectedValue(new Error(''))

        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /google/i }))

        await waitFor(() => {
            expect(screen.getByText('Google sign-in failed.')).toBeInTheDocument()
        })

        delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
    })
})
