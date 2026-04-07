import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Page from '../../../src/app/schema/page'

const mockSchemaPageRender = vi.fn()
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

vi.mock('../../../src/app/schema/SchemaPage', () => ({
    default: () => {
        mockSchemaPageRender()
        return (
            <div data-testid="schema-page">
                <h1>SchemaPage Component</h1>
                <p data-testid="component-type">Mocked Schema Component</p>
            </div>
        )
    }
}))

describe('Schema Page Route Guard', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockGetValidAccessToken.mockResolvedValue('mock-token')
    })

    it('renders SchemaPage when access token exists', async () => {
        render(<Page />)

        await waitFor(() => {
            expect(screen.getByTestId('schema-page')).toBeInTheDocument()
        })

        expect(mockReplace).not.toHaveBeenCalled()
        expect(mockSchemaPageRender).toHaveBeenCalledTimes(1)
    })

    it('redirects to login when access token is missing', async () => {
        mockGetValidAccessToken.mockResolvedValue(null)

        const { container } = render(<Page />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })

        expect(screen.queryByTestId('schema-page')).not.toBeInTheDocument()
        expect(container.firstChild).toBeNull()
        expect(mockSchemaPageRender).not.toHaveBeenCalled()
    })

    it('does not redirect after unmount when async auth check resolves late', async () => {
        let resolveToken: ((value: string | null) => void) | null = null
        const pendingToken = new Promise<string | null>((resolve) => {
            resolveToken = resolve
        })
        mockGetValidAccessToken.mockReturnValue(pendingToken)

        const { unmount } = render(<Page />)
        unmount()

        resolveToken?.(null)
        await Promise.resolve()

        expect(mockReplace).not.toHaveBeenCalled()
        expect(mockSchemaPageRender).not.toHaveBeenCalled()
    })
})
