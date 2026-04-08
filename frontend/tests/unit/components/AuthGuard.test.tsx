import { act, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AuthGuard from '@/components/AuthGuard'

const mockReplace = vi.fn()
const mockGetValidAccessToken = vi.fn<() => Promise<string | null>>()
const mockRouter = { replace: mockReplace }
let mockPathname = '/convert'

vi.mock('next/navigation', () => ({
    useRouter: () => mockRouter,
    usePathname: () => mockPathname,
}))

vi.mock('@/lib/auth', () => ({
    getValidAccessToken: () => mockGetValidAccessToken(),
}))

describe('AuthGuard', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockPathname = '/convert'
        mockGetValidAccessToken.mockResolvedValue('valid-token')
    })

    it('renders children when a valid token exists', async () => {
        render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(screen.getByTestId('protected-content')).toBeInTheDocument()
        })

        expect(mockReplace).not.toHaveBeenCalled()
    })

    it('redirects to /login and hides children when token is missing', async () => {
        mockGetValidAccessToken.mockResolvedValue(null)

        const { container } = render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })

        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
        expect(container.firstChild).toBeNull()
    })

    it('supports custom redirect and loading fallback', async () => {
        let resolveToken: ((value: string | null) => void) | undefined
        mockGetValidAccessToken.mockReturnValue(
            new Promise<string | null>((resolve) => {
                resolveToken = resolve
            })
        )

        render(
            <AuthGuard redirectTo="/auth/sign-in" loadingFallback={<div data-testid="loading">Checking access</div>}>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        expect(screen.getByTestId('loading')).toBeInTheDocument()

        resolveToken?.(null)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/auth/sign-in')
        })
    })

    it('re-checks access when the pathname changes', async () => {
        const { rerender } = render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(screen.getByTestId('protected-content')).toBeInTheDocument()
        })

        mockPathname = '/schema'
        rerender(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(mockGetValidAccessToken.mock.calls.length).toBeGreaterThanOrEqual(2)
        })
    })

    it('forces a redirect when browser back navigation restores a protected page after logout', async () => {
        render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(screen.getByTestId('protected-content')).toBeInTheDocument()
        })

        mockGetValidAccessToken.mockResolvedValue(null)
        await act(async () => {
            window.dispatchEvent(new PopStateEvent('popstate'))
        })

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })
    })

    it('re-checks access when the page is restored from browser cache', async () => {
        render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        await waitFor(() => {
            expect(screen.getByTestId('protected-content')).toBeInTheDocument()
        })

        mockGetValidAccessToken.mockResolvedValue(null)
        await act(async () => {
            window.dispatchEvent(new Event('pageshow'))
        })

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })
    })

    it('does not update state or redirect after unmount when auth check resolves late', async () => {
        let resolveToken: ((value: string | null) => void) | undefined
        mockGetValidAccessToken.mockReturnValue(
            new Promise<string | null>((resolve) => {
                resolveToken = resolve
            })
        )

        const { unmount } = render(
            <AuthGuard>
                <div data-testid="protected-content">Protected Content</div>
            </AuthGuard>
        )

        unmount()
        resolveToken?.(null)
        await Promise.resolve()

        expect(mockReplace).not.toHaveBeenCalled()
    })
})
