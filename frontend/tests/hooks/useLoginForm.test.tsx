import { renderHook, act } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import useLoginForm from '../../src/hooks/useLoginForm'
import * as api from '@/lib/api'

const mockStoreAuthTokens = vi.fn()
const mockGoogleSignIn = vi.fn()
const mockUseGoogleLogin = vi.fn()

vi.mock('@react-oauth/google', () => ({
    useGoogleLogin: (...args: unknown[]) => mockUseGoogleLogin(...args),
}))

vi.mock('@/lib/api', () => ({
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
}))

vi.mock('@/lib/auth', async () => {
    const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth')

    return {
        ...actual,
        storeAuthTokens: (...args: unknown[]) => mockStoreAuthTokens(...args),
    }
})

describe('useLoginForm', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers()
        mockUseGoogleLogin.mockReturnValue(mockGoogleSignIn)
        window.localStorage.clear()
        window.sessionStorage.clear()
        Object.defineProperty(globalThis, 'location', {
            value: { href: '' },
            writable: true,
            configurable: true,
        })
        process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = 'mock-client-id'
    })

    it('initializes with controlled form defaults', () => {
        const { result } = renderHook(() => useLoginForm())

        expect(result.current.email).toBe('')
        expect(result.current.password).toBe('')
        expect(result.current.error).toBeNull()
        expect(result.current.success).toBeNull()
        expect(result.current.isLoading).toBe(false)
        expect(result.current.isFormDisabled).toBe(false)
    })

    it('updates email and password', () => {
        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        expect(result.current.email).toBe('test@example.com')
        expect(result.current.password).toBe('secret123')
    })

    it('sets validation error for invalid email', async () => {
        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('invalid-email')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Please enter a valid email address.')
        expect(api.login).not.toHaveBeenCalled()
    })

    it('sets validation error for blank password', async () => {
        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('   ')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Password is required.')
        expect(api.login).not.toHaveBeenCalled()
    })

    it('calls login API and stores auth data on successful login', async () => {
        vi.mocked(api.login).mockResolvedValueOnce({
            access_token: 'access-token',
            refresh_token: 'refresh-token',
            user: { id: 1, name: 'Test User', email: 'test@example.com' },
        })

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(api.login).toHaveBeenCalledWith('test@example.com', 'secret123')
        expect(result.current.success).toContain(`You're being redirected`)
        expect(result.current.isFormDisabled).toBe(true)
        expect(mockStoreAuthTokens).toHaveBeenCalledWith('access-token', 'refresh-token')
        expect(window.localStorage.getItem('user_name')).toBe('Test User')
        expect(window.localStorage.getItem('user_email')).toBe('test@example.com')

        await act(async () => {
            vi.advanceTimersByTime(2000)
        })

        expect(globalThis.location.href).toBe('/convert')
    })

    it('surfaces API error on failed login', async () => {
        vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Invalid credentials')
        expect(result.current.isLoading).toBe(false)
        expect(result.current.success).toBeNull()
    })

    it('uses fallback message when login throws Error with empty message', async () => {
        vi.mocked(api.login).mockRejectedValueOnce(new Error(''))

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Login failed. Please try again.')
        expect(result.current.isLoading).toBe(false)
    })

    it('uses generic fallback when login throws non-Error value', async () => {
        vi.mocked(api.login).mockRejectedValueOnce('network down')

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Something went wrong')
        expect(result.current.isLoading).toBe(false)
    })

    it('handles successful login response without user profile payload', async () => {
        vi.mocked(api.login).mockResolvedValueOnce({
            access_token: 'access-no-user',
            refresh_token: 'refresh-no-user',
        } as never)

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(mockStoreAuthTokens).toHaveBeenCalledWith('access-no-user', 'refresh-no-user')
        expect(window.localStorage.getItem('user_name')).toBeNull()
        expect(window.localStorage.getItem('user_email')).toBeNull()
    })

    it('shows Google config error when client id is missing', () => {
        delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.triggerGoogleSignIn()
        })

        expect(result.current.error).toContain('NEXT_PUBLIC_GOOGLE_CLIENT_ID')
        expect(mockGoogleSignIn).not.toHaveBeenCalled()
    })

    it('runs google sign-in callback and stores auth data on success', async () => {
        let googleOptions: {
            onSuccess?: (tokenResponse: { access_token: string }) => void | Promise<void>
        } = {}

        mockUseGoogleLogin.mockImplementation((options) => {
            googleOptions = options as typeof googleOptions
            return mockGoogleSignIn
        })

        vi.mocked(api.loginWithGoogle).mockResolvedValueOnce({
            access_token: 'google-access',
            refresh_token: 'google-refresh',
            user: { id: 1, name: 'Google User', email: 'google@example.com' },
        })

        renderHook(() => useLoginForm())

        await act(async () => {
            await googleOptions.onSuccess?.({ access_token: 'google-token' })
        })

        expect(api.loginWithGoogle).toHaveBeenCalledWith('google-token')
        expect(mockStoreAuthTokens).toHaveBeenCalledWith('google-access', 'google-refresh')
    })

    it('calls googleSignIn when client id is configured', () => {
        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.triggerGoogleSignIn()
        })

        expect(mockGoogleSignIn).toHaveBeenCalledTimes(1)
    })

    it('sets cancellation error when google oauth onError is fired', async () => {
        let googleOptions: {
            onError?: () => void
        } = {}

        mockUseGoogleLogin.mockImplementation((options) => {
            googleOptions = options as typeof googleOptions
            return mockGoogleSignIn
        })

        const { result } = renderHook(() => useLoginForm())

        await act(async () => {
            googleOptions.onError?.()
        })

        expect(result.current.error).toBe('Google sign-in cancelled or failed')
    })

    it('surfaces google sign-in API error when oauth success callback fails', async () => {
        let googleOptions: {
            onSuccess?: (tokenResponse: { access_token: string }) => void | Promise<void>
        } = {}

        mockUseGoogleLogin.mockImplementation((options) => {
            googleOptions = options as typeof googleOptions
            return mockGoogleSignIn
        })

        vi.mocked(api.loginWithGoogle).mockRejectedValueOnce(new Error('Google auth failed'))

        const { result } = renderHook(() => useLoginForm())

        await act(async () => {
            await googleOptions.onSuccess?.({ access_token: 'google-token' })
        })

        expect(result.current.error).toBe('Google auth failed')
        expect(result.current.isLoading).toBe(false)
    })

    it('clears feedback through dismiss handlers', async () => {
        vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

        const { result } = renderHook(() => useLoginForm())

        act(() => {
            result.current.handleEmailChange('test@example.com')
            result.current.handlePasswordChange('secret123')
        })

        await act(async () => {
            await result.current.handleLogin()
        })

        expect(result.current.error).toBe('Invalid credentials')

        act(() => {
            result.current.dismissError()
            result.current.dismissSuccess()
        })

        expect(result.current.error).toBeNull()
        expect(result.current.success).toBeNull()
    })
})
