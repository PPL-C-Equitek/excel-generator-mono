import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LogoutButton from '@/components/LogoutButton'
import { withProtectedPage } from '@/lib/withProtectedPage'
import * as api from '@/lib/api'

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockLogout = vi.spyOn(api, 'logout')

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
        mockLogout.mockResolvedValue()
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
            expect(mockLogout).toHaveBeenCalledWith('access-token', 'refresh-token')
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

        mockLogout.mockRejectedValueOnce(new Error('Unauthorized'))

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(screen.getByRole('status')).toHaveTextContent('Unauthorized')
        })

        expect(window.localStorage.getItem('access_token')).toBe('access-token')
        expect(window.localStorage.getItem('refresh_token')).toBe('refresh-token')
        expect(mockPush).not.toHaveBeenCalled()
    })

    it('shows the backend detail message when logout fails with detail only', async () => {
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockLogout.mockRejectedValueOnce(new Error('Token invalid'))

        render(<LogoutButton />)

        await user.click(screen.getByRole('button', { name: /logout/i }))

        await waitFor(() => {
            expect(screen.getByRole('status')).toHaveTextContent('Token invalid')
        })
    })

    it('falls back to the generic error when logout throws a non-Error value', async () => {
        const user = userEvent.setup()

        window.localStorage.setItem('access_token', 'access-token')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        mockLogout.mockRejectedValueOnce('unexpected')

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

        mockLogout.mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolveRequest = () => resolve()
                })
        )

        render(<LogoutButton />)

        const button = screen.getByRole('button', { name: /logout/i })
        const firstClick = user.click(button)
        await waitFor(() => {
            expect(button).toBeDisabled()
        })
        const secondClick = user.click(button)

        expect(mockLogout).toHaveBeenCalledTimes(1)

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
})
