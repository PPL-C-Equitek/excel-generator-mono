import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Page from '../../../src/app/convert/page'

const mockConvertPageRender = vi.fn()
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

vi.mock('../../../src/app/convert/ConvertPage', () => ({
    default: () => {
        mockConvertPageRender()
        return <div data-testid="convert-page">Mocked ConvertPage</div>
    }
}))

describe('Convert Page Route Guard', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockGetValidAccessToken.mockResolvedValue('mock-token')
    })

    it('renders ConvertPage when access token exists', async () => {
        render(<Page />)

        await waitFor(() => {
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
        })

        expect(mockReplace).not.toHaveBeenCalled()
        expect(mockConvertPageRender).toHaveBeenCalledTimes(1)
    })

    it('redirects to login when access token is missing', async () => {
        mockGetValidAccessToken.mockResolvedValue(null)

        const { container } = render(<Page />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })

        expect(screen.queryByTestId('convert-page')).not.toBeInTheDocument()
        expect(container.firstChild).toBeNull()
        expect(mockConvertPageRender).not.toHaveBeenCalled()
    })
})
