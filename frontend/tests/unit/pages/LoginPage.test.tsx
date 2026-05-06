import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGoogleLogin } from '@react-oauth/google'
import LoginPage from '../../../src/app/login/LoginPage'
import * as api from '@/lib/api'

const mockHasValidSession = vi.fn<() => Promise<boolean>>()
const mockStoreAuthTokens = vi.fn((accessToken: string, refreshToken: string) => {
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    sessionStorage.setItem('access_token', accessToken)
    sessionStorage.setItem('refresh_token', refreshToken)
})

vi.mock('@react-oauth/google', () => ({
    useGoogleLogin: vi.fn(() => vi.fn()),
}))

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

vi.mock('@/lib/api', () => ({
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
}))

vi.mock('@/lib/auth', async () => {
    const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth')

    return {
        ...actual,
        hasValidSession: () => mockHasValidSession(),
        storeAuthTokens: (accessToken: string, refreshToken: string) =>
            mockStoreAuthTokens(accessToken, refreshToken),
    }
})

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useRealTimers()
        window.localStorage.clear()
        window.sessionStorage.clear()
        mockHasValidSession.mockResolvedValue(false)
        Object.defineProperty(globalThis, 'location', {
            value: { href: '' },
            writable: true,
            configurable: true,
        })
    })

    it('renders navbar and login form shell', () => {
        render(<LoginPage />)

        expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument()
    })

    it('shows validation message when form is empty', async () => {
        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(await screen.findByText('Please enter a valid email address.')).toBeInTheDocument()
        expect(api.login).not.toHaveBeenCalled()
    })

    it('stores tokens and redirects after successful credentials login', async () => {
        const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

        vi.mocked(api.login).mockResolvedValueOnce({
            access_token: 'mock-access',
            refresh_token: 'mock-refresh',
            user: { id: 1, name: 'User 1', email: 'user1@gmail.com' },
        })

        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'user1@gmail.com' },
        })
        fireEvent.change(screen.getByLabelText(/password/i), {
            target: { value: 'user1123' },
        })
        fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        await waitFor(() => {
            expect(api.login).toHaveBeenCalledWith('user1@gmail.com', 'user1123')
            expect(screen.getByText(/welcome back!/i)).toBeInTheDocument()
            expect(localStorage.getItem('user_name')).toBe('User 1')
            expect(localStorage.getItem('user_email')).toBe('user1@gmail.com')
        })

        await waitFor(() => {
            expect(mockStoreAuthTokens).toHaveBeenCalledWith('mock-access', 'mock-refresh')
        })

        expect(setTimeoutSpy).toHaveBeenCalled()
        expect(globalThis.location.href).not.toBe('/convert')
    })

    it('renders API error inline when credentials login fails', async () => {
        vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'user1@gmail.com' },
        })
        fireEvent.change(screen.getByLabelText(/password/i), {
            target: { value: 'wrongpassword' },
        })
        fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(await screen.findByText('Invalid credentials')).toBeInTheDocument()
        expect(globalThis.location.href).not.toBe('/convert')
    })

    it('shows missing google client id message inline', async () => {
        const originalEnv = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
        delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID

        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /google/i }))

        expect(
            await screen.findByText(/NEXT_PUBLIC_GOOGLE_CLIENT_ID/i)
        ).toBeInTheDocument()

        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = originalEnv
    })

    it('stores tokens and redirects on successful google sign-in', async () => {
        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'mock-client-id'
        const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')

        vi.mocked(useGoogleLogin).mockImplementation((options) => {
            return () => {
                void options.onSuccess?.({ access_token: 'google-token' } as never)
            }
        })

        vi.mocked(api.loginWithGoogle).mockResolvedValueOnce({
            access_token: 'google-access',
            refresh_token: 'google-refresh',
            user: { id: 1, name: 'Google User', email: 'google@example.com' },
        })

        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }))

        await waitFor(() => {
            expect(api.loginWithGoogle).toHaveBeenCalledWith('google-token')
            expect(mockStoreAuthTokens).toHaveBeenCalledWith('google-access', 'google-refresh')
            expect(screen.getByText(/welcome!/i)).toBeInTheDocument()
        })

        expect(setTimeoutSpy).toHaveBeenCalled()
        expect(globalThis.location.href).not.toBe('/convert')
    })

    it('renders google failure inline when oauth request fails', async () => {
        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'mock-client-id'

        vi.mocked(useGoogleLogin).mockImplementation((options) => {
            return () => {
                void options.onSuccess?.({ access_token: 'google-token' } as never)
            }
        })

        vi.mocked(api.loginWithGoogle).mockRejectedValueOnce(new Error('Google auth failed'))

        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }))

        expect(await screen.findByText('Google auth failed')).toBeInTheDocument()
    })

    it('renders google cancellation error inline when oauth onError fires', async () => {
        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'mock-client-id'

        vi.mocked(useGoogleLogin).mockImplementation((options) => {
            return () => {
                void options.onError?.({} as never)
            }
        })

        render(<LoginPage />)

        fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }))

        expect(await screen.findByText('Google sign-in cancelled or failed')).toBeInTheDocument()
    })
})
