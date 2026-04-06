import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import LoginPage from '../../../src/app/login/LoginPage'
import * as api from '@/lib/api'

vi.mock('@react-oauth/google', () => ({
    useGoogleLogin: vi.fn(() => vi.fn()),
}))

describe('LoginPage', () => {
    describe('positive', () => {
        it('renders Navbar', () => {
            render(<LoginPage />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('renders Login as active in Navbar', () => {
            render(<LoginPage />)
            const loginLink = screen.getAllByText('Login')[0]
            expect(loginLink).toHaveClass('font-bold')
        })

        it('renders LoginForm inside page', () => {
            render(<LoginPage />)
            expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument()
        })

        it('renders page with light background', () => {
            const { container } = render(<LoginPage />)
            expect(container.firstChild).toHaveClass('force-light')
        })

        it('renders page with min-h-screen', () => {
            const { container } = render(<LoginPage />)
            expect(container.firstChild).toHaveClass('min-h-screen')
        })
    })

    describe('negative', () => {
        it('does not render sidebar', () => {
            render(<LoginPage />)
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByText('History')).not.toBeInTheDocument()
        })

        it('does not render hero section', () => {
            render(<LoginPage />)
            expect(screen.queryByTestId('hero-section')).not.toBeInTheDocument()
        })

        it('does not render upload zone', () => {
            render(<LoginPage />)
            expect(screen.queryByTestId('drop-zone')).not.toBeInTheDocument()
        })
    })

    describe('edge case', () => {
        beforeEach(() => {
            vi.clearAllMocks()
            localStorage.clear()
            vi.spyOn(window, 'alert').mockImplementation(() => { })
            Object.defineProperty(globalThis, 'location', {
                value: { href: '' },
                writable: true,
            })
        })

        it('does not call login API when form is submitted empty', async () => {
            render(<LoginPage />)

            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(api.login).not.toHaveBeenCalled()
            })
        })

        it('does not save tokens to localStorage when login fails', async () => {
            vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'wrongpassword' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(localStorage.getItem('access_token')).toBeNull()
                expect(localStorage.getItem('refresh_token')).toBeNull()
            })
        })

        it('does not redirect when login fails', async () => {
            vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'wrongpassword' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(globalThis.location.href).not.toBe('/convert')
            })
        })
    })
})

// Mock api module
vi.mock('@/lib/api', () => ({
    login: vi.fn(),
    loginWithGoogle: vi.fn(),
}))

describe('handleLogin', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        localStorage.clear()

        // Spy alert & location
        vi.spyOn(window, 'alert').mockImplementation(() => { })
        Object.defineProperty(globalThis, 'location', {
            value: { href: '' },
            writable: true,
        })
    })

    it('saves tokens to localStorage and redirects on successful login', async () => {
        vi.mocked(api.login).mockResolvedValueOnce({
            access_token: 'mock-access',
            refresh_token: 'mock-refresh',
        })

        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'user1@gmail.com' },
        })
        fireEvent.change(screen.getByLabelText(/password/i), {
            target: { value: 'user1123' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

        await waitFor(() => {
            expect(localStorage.getItem('access_token')).toBe('mock-access')
            expect(localStorage.getItem('refresh_token')).toBe('mock-refresh')
            expect(globalThis.location.href).toBe('/convert')
        })
    })

    it('alerts error message when login throws an Error', async () => {
        vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'user1@gmail.com' },
        })
        fireEvent.change(screen.getByLabelText(/password/i), {
            target: { value: 'wrongpassword' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

        await waitFor(() => {
            expect(window.alert).toHaveBeenCalledWith('Invalid credentials')
        })
    })

    it('alerts fallback message when login throws a non-Error', async () => {
        vi.mocked(api.login).mockRejectedValueOnce('unexpected string error')

        render(<LoginPage />)

        fireEvent.change(screen.getByLabelText(/email/i), {
            target: { value: 'user1@gmail.com' },
        })
        fireEvent.change(screen.getByLabelText(/password/i), {
            target: { value: 'user1123' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

        await waitFor(() => {
            expect(window.alert).toHaveBeenCalledWith('Something went wrong')
        })
    })

    describe('edge case', () => {
        it('calls login API with correct email and password', async () => {
            vi.mocked(api.login).mockResolvedValueOnce({
                access_token: 'mock-access',
                refresh_token: 'mock-refresh',
            })

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'user1123' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(api.login).toHaveBeenCalledWith('user1@gmail.com', 'user1123')
            })
        })

        it('does not alert when login succeeds', async () => {
            vi.mocked(api.login).mockResolvedValueOnce({
                access_token: 'mock-access',
                refresh_token: 'mock-refresh',
            })

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'user1123' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(globalThis.location.href).toBe('/convert')
            })

            expect(window.alert).not.toHaveBeenCalled()
        })

        it('does not redirect when login throws an Error', async () => {
            vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'wrongpassword' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(window.alert).toHaveBeenCalledWith('Invalid credentials')
            })

            expect(globalThis.location.href).not.toBe('/convert')
        })

        it('overwrites existing tokens in localStorage on re-login', async () => {
            localStorage.setItem('access_token', 'old-access')
            localStorage.setItem('refresh_token', 'old-refresh')

            vi.mocked(api.login).mockResolvedValueOnce({
                access_token: 'new-access',
                refresh_token: 'new-refresh',
            })

            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), {
                target: { value: 'user1@gmail.com' },
            })
            fireEvent.change(screen.getByLabelText(/password/i), {
                target: { value: 'user1123' },
            })
            fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

            await waitFor(() => {
                expect(localStorage.getItem('access_token')).toBe('new-access')
                expect(localStorage.getItem('refresh_token')).toBe('new-refresh')
            })
        })
    })
})