import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Page from '../../../src/app/convert/page'

const mockConvertPageRender = vi.fn()
const mockReplace = vi.fn()
const mockGetStoredAccessToken = vi.fn<() => string | null>()

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        replace: mockReplace,
    }),
}))

vi.mock('@/lib/auth', () => ({
    getStoredAccessToken: () => mockGetStoredAccessToken(),
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
        mockGetStoredAccessToken.mockReturnValue('mock-token')
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
        mockGetStoredAccessToken.mockReturnValue(null)

        const { container } = render(<Page />)

        await waitFor(() => {
            expect(mockReplace).toHaveBeenCalledWith('/login')
        })

        expect(screen.queryByTestId('convert-page')).not.toBeInTheDocument()
        expect(container.firstChild).toBeNull()
        expect(mockConvertPageRender).not.toHaveBeenCalled()
    })
})
