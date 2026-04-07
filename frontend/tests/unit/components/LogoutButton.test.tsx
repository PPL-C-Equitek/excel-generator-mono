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
            expect(mockFetch).toHaveBeenCalledWith('/auth/logout/', {
                method: 'POST',
            })
        })

        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
        expect(screen.getByRole('status')).toHaveTextContent('Berhasil keluar')
        expect(mockPush).toHaveBeenCalledWith('/')
    })

    it('disables the button and prevents duplicate logout requests during rapid double click', async () => {
        const user = userEvent.setup()
        let resolveRequest: (() => void) | undefined

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
})
