import { render, screen } from '@testing-library/react'
import { act } from '@testing-library/react'
import { beforeEach, describe, it, expect } from 'vitest'
import { vi } from 'vitest'
import Navbar from '../../../src/components/Navbar'
import * as authModule from '../../../src/lib/auth'
import { AUTH_STATE_CHANGE_EVENT } from '../../../src/lib/auth'
import type { NavLink } from '../../../src/constants/landing'

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

// Mock data for testing - demonstrates DIP principle
const mockNavLinks: NavLink[] = [
    { label: 'Login', href: '/login', key: 'login' },
    { label: 'Register', href: '/register', key: 'register' },
]

describe('Navbar', () => {
    beforeEach(() => {
        vi.restoreAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    // Positive tests
    describe('positive', () => {
        it('renders brand name EQUITEK by default', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('links brand name to home', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('EQUITEK')).toHaveAttribute('href', '/')
        })

        it('renders custom brand name when provided', () => {
            render(<Navbar links={mockNavLinks} brandName="CUSTOM BRAND" />)
            expect(screen.getByText('CUSTOM BRAND')).toBeInTheDocument()
        })

        it('renders provided navigation links', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
        })

        it('Login links to /login', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Login')).toHaveAttribute('href', '/login')
        })

        it('Register links to /register', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Register')).toHaveAttribute('href', '/register')
        })

        it('renders nav element as wrapper', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByRole('navigation')).toBeInTheDocument()
        })

        it('renders custom links when different NavLink array provided', () => {
            const customLinks: NavLink[] = [
                { label: 'Home', href: '/', key: 'login' },
                { label: 'About', href: '/about', key: 'register' },
            ]
            render(<Navbar links={customLinks} />)
            expect(screen.getByText('Home')).toBeInTheDocument()
            expect(screen.getByText('About')).toBeInTheDocument()
            expect(screen.queryByText('Login')).not.toBeInTheDocument()
        })
    })

    // Negative tests
    describe('negative', () => {
        it('does not render a Logout button', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByText('Logout')).not.toBeInTheDocument()
        })

        it('does not render a sidebar menu', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByText('History')).not.toBeInTheDocument()
        })

        it('does not render any button element', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByRole('button')).not.toBeInTheDocument()
        })

        it('does not render empty brand name', () => {
            render(<Navbar links={mockNavLinks} />)
            const brand = screen.getByText('EQUITEK')
            expect(brand.textContent).not.toBe('')
        })

        it('does not render links that are not in the provided array', () => {
            const minimalLinks: NavLink[] = [
                { label: 'Home', href: '/', key: 'login' }
            ]
            render(<Navbar links={minimalLinks} />)
            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
        })

        it('does not render Login and Register links when user is already authenticated', async () => {
            window.localStorage.setItem('access_token', 'existing-token')
            window.localStorage.setItem('refresh_token', 'refresh-token')
            vi.spyOn(authModule, 'hasValidSession').mockResolvedValue(true)

            render(<Navbar links={mockNavLinks} />)

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
            expect(screen.getByText('Convert')).toBeInTheDocument()
            expect(screen.getByText('Schema')).toBeInTheDocument()
            expect(screen.getByText('History')).toBeInTheDocument()
            expect(screen.queryByText('Change Password')).not.toBeInTheDocument()
            expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
        })

        it('updates the navbar immediately when auth state changes on the current page', async () => {
            window.localStorage.setItem('access_token', 'existing-token')
            window.localStorage.setItem('refresh_token', 'refresh-token')
            const hasValidSessionSpy = vi.spyOn(authModule, 'hasValidSession')
            hasValidSessionSpy.mockResolvedValueOnce(true)
            hasValidSessionSpy.mockResolvedValueOnce(false)

            render(<Navbar links={mockNavLinks} />)

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()

            window.localStorage.removeItem('access_token')

            await act(async () => {
                window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT))
                await Promise.resolve()
            })

            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
        })

        it('keeps guest navbar when an older auth check resolves after a newer state change', async () => {
            window.localStorage.setItem('access_token', 'existing-token')
            window.localStorage.setItem('refresh_token', 'refresh-token')

            let resolveFirstCheck: ((value: boolean) => void) | null = null
            const firstCheck = new Promise<boolean>((resolve) => {
                resolveFirstCheck = resolve
            })

            const hasValidSessionSpy = vi.spyOn(authModule, 'hasValidSession')
            hasValidSessionSpy
                .mockImplementationOnce(() => firstCheck)
                .mockResolvedValueOnce(false)

            render(<Navbar links={mockNavLinks} />)

            window.localStorage.removeItem('access_token')
            window.localStorage.removeItem('refresh_token')

            act(() => {
                window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT))
            })

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()

            if (resolveFirstCheck) {
                await act(async () => {
                    resolveFirstCheck(true)
                    await Promise.resolve()
                })
            }

            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(hasValidSessionSpy).toHaveBeenCalledTimes(2)
        })

        it('falls back to guest navbar when stored token is invalid or unauthorized', async () => {
            window.localStorage.setItem('access_token', 'manually-inserted-invalid-token')
            window.localStorage.setItem('refresh_token', 'stale-refresh-token')

            vi.spyOn(authModule, 'hasValidSession').mockResolvedValue(false)

            render(<Navbar links={mockNavLinks} />)

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument()
        })

        it('falls back to guest navbar when only an access token remains in storage', async () => {
            window.localStorage.setItem('access_token', 'orphan-access-token')

            const hasValidSessionSpy = vi.spyOn(authModule, 'hasValidSession').mockResolvedValue(false)

            render(<Navbar links={mockNavLinks} />)

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument()
            expect(hasValidSessionSpy).toHaveBeenCalledTimes(1)
        })
    })
})
