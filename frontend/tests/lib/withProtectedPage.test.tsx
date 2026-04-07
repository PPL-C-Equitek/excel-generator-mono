import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { withProtectedPage } from '../../src/lib/withProtectedPage'
import type { ComponentType } from 'react'

const mockReplace = vi.fn()
const mockGetValidAccessToken = vi.fn<() => Promise<string | null>>()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace: mockReplace,
    }),
}))

vi.mock('@/lib/auth', () => ({
    getValidAccessToken: () => mockGetValidAccessToken(),
}))

function DummyPage() {
    return <div data-testid="dummy-page">Protected Content</div>
}

describe('withProtectedPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockGetValidAccessToken.mockResolvedValue('valid-token')
    })

    it('renders wrapped page when valid access token exists', async () => {
        const ProtectedPage = withProtectedPage(DummyPage)

        render(<ProtectedPage />)

        await waitFor(() => {
            expect(screen.getByTestId('dummy-page')).toBeInTheDocument()
        })

        expect(mockReplace).not.toHaveBeenCalled()
    })

    it('redirects to /login when token is missing', async () => {
        const ProtectedPage = withProtectedPage(DummyPage)
        mockGetValidAccessToken.mockResolvedValue(null)

        const { container } = render(<ProtectedPage />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })

        expect(screen.queryByTestId('dummy-page')).not.toBeInTheDocument()
        expect(container.firstChild).toBeNull()
    })

    it('supports custom redirect path', async () => {
        const ProtectedPage = withProtectedPage(DummyPage, { redirectTo: '/auth/sign-in' })
        mockGetValidAccessToken.mockResolvedValue(null)

        render(<ProtectedPage />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/auth/sign-in')
        })
    })

    it('does not redirect after unmount when auth check resolves late', async () => {
        const ProtectedPage = withProtectedPage(DummyPage)
        let resolveToken: ((value: string | null) => void) | undefined
        const pendingToken = new Promise<string | null>((resolve) => {
            resolveToken = resolve
        })
        mockGetValidAccessToken.mockReturnValue(pendingToken)

        const { unmount } = render(<ProtectedPage />)
        unmount()

        if (resolveToken) {
            resolveToken(null)
        }
        await Promise.resolve()

        expect(mockReplace).not.toHaveBeenCalled()
    })

    describe('edge case', () => {
        it('sets displayName to fallback when component has no displayName or name', () => {
            const AnonymousComponent = Object.assign(
                (() => <div />) as ComponentType,
                { displayName: undefined }
            ) as ComponentType & { name: string }
            Object.defineProperty(AnonymousComponent, 'name', { value: '' })

            const ProtectedPage = withProtectedPage(AnonymousComponent)

            expect(ProtectedPage.displayName).toBe('withProtectedPage(Component)')
        })

        it('sets displayName using component name when displayName is not set', () => {
            const ProtectedPage = withProtectedPage(DummyPage)

            expect(ProtectedPage.displayName).toBe('withProtectedPage(DummyPage)')
        })

        it('sets displayName to fallback when component has no displayName or name', () => {
            const ProtectedPage = withProtectedPage(() => <div />)

            expect(ProtectedPage.displayName).toBe('withProtectedPage(Component)')
        })
    })
})
