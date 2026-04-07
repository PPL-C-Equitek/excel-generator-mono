import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LogoutButton from '@/components/LogoutButton'
import { withProtectedPage } from '@/lib/withProtectedPage'

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockFetch = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: mockPush,
        replace: mockReplace,
    }),
}))

describe('LogoutButton', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
        document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
        document.cookie = 'refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
        document.cookie = 'accessToken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
        document.cookie = 'refreshToken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'

        vi.stubGlobal('fetch', mockFetch)
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ detail: 'Logged out successfully' }),
        })
    })

    it('renders an accessible logout button', () => {
        render(<LogoutButton />)

        expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
    })

    it('calls POST /auth/logout/, clears auth state, shows success notification, and redirects to homepage', async () => {
        const user = userEvent.setup()
        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')
        document.cookie = 'access_token=cookie-access-token; path=/'
        document.cookie = 'refresh_token=cookie-refresh-token; path=/'

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringMatching(/\/auth\/logout\/$/),
                expect.objectContaining({
                    method: 'POST',
                    headers: expect.objectContaining({
                        Authorization: 'Bearer access-token',
                        'Content-Type': 'application/json',
                    }),
                    body: JSON.stringify({
                        refresh_token: 'refresh-token',
                    }),
                })
            )
        })

        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
        expect(screen.getByRole('status')).toHaveTextContent('Berhasil keluar')
        expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('shows an error message and keeps auth state when logout fails on the server', async () => {
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockFetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ message: 'Unauthorized' }),
        })

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(screen.getByRole('status')).toHaveTextContent(
                'Logout gagal. Silakan coba lagi.'
            )
        })

        expect(window.localStorage.getItem('access_token')).toBe('access-token')
        expect(window.localStorage.getItem('refresh_token')).toBe('refresh-token')
        expect(mockPush).not.toHaveBeenCalled()
    })

    it('shows the backend detail message when logout fails with detail only', async () => {
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockFetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ detail: 'Token invalid' }),
        })

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(screen.getByRole('status')).toHaveTextContent(
                'Logout gagal. Silakan coba lagi.'
            )
        })
    })

    it('falls back to the generic error when logout response body cannot be parsed', async () => {
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockFetch.mockResolvedValueOnce({
            ok: false,
            json: async () => {
                throw new Error('invalid json')
            },
        })

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(screen.getByRole('status')).toHaveTextContent(
                'Logout gagal. Silakan coba lagi.'
            )
        })
    })

    it('disables the button and prevents duplicate logout requests during rapid double click', async () => {
        const user = userEvent.setup()
        let resolveRequest: (() => void) | undefined

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockFetch.mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolveRequest = () =>
                        resolve({
                            ok: true,
                            json: async () => ({ detail: 'Logged out successfully' }),
                        })
                })
        )

        render(<LogoutButton />)

        const button = screen.getByRole('button', { name: /logout/i })
        const firstClick = user.click(button)
        await waitFor(() => {
            expect(button).toBeDisabled()
        })
        const secondClick = user.click(button)

        expect(mockFetch).toHaveBeenCalledTimes(1)

        resolveRequest?.()
        await firstClick
        await secondClick
    })

    it('redirects protected pages to /login when there is no token after logout', async () => {
        const user = userEvent.setup()
        window.localStorage.setItem('access_token', 'access-token')

        function DummyPage() {
            return <div data-testid="dummy-page">Protected Content</div>
        }

        const ProtectedPage = withProtectedPage(DummyPage)

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        render(<ProtectedPage />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })
    })

    it('normalizes a trailing slash in the API base URL', async () => {
        vi.unstubAllGlobals()
        vi.resetModules()

        const previousApiUrl = process.env.NEXT_PUBLIC_API_URL
        process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/'

        const { default: LogoutButtonWithSlash } = await import('@/components/LogoutButton')
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        const trailingSlashFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ detail: 'Logged out successfully' }),
        })
        vi.stubGlobal('fetch', trailingSlashFetch)

        render(<LogoutButtonWithSlash />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(trailingSlashFetch).toHaveBeenCalledWith(
                'http://localhost:8000/auth/logout/',
                expect.objectContaining({ method: 'POST' })
            )
        })

        process.env.NEXT_PUBLIC_API_URL = previousApiUrl
    })
})
