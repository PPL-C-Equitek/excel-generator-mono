import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Page from '../../../src/app/convert/page'

const mockConvertPageRender = vi.fn()
const mockAuthGuardRender = vi.fn()
const mockAuthGuardProps = vi.fn()

vi.mock('@/components/AuthGuard', () => ({
    default: ({ children }: { children: React.ReactNode }) => {
        mockAuthGuardRender()
        mockAuthGuardProps(children)
        return <div data-testid="auth-guard">{children}</div>
    },
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
    })

    it('renders ConvertPage inside AuthGuard', async () => {
        render(<Page />)

        await waitFor(() => {
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
        })

        expect(screen.getByTestId('auth-guard')).toBeInTheDocument()
        expect(mockAuthGuardRender).toHaveBeenCalledTimes(1)
        expect(mockConvertPageRender).toHaveBeenCalledTimes(1)
    })

    it('passes ConvertPage as AuthGuard children', () => {
        render(<Page />)

        expect(mockAuthGuardProps).toHaveBeenCalled()
        expect(screen.getByTestId('convert-page')).toBeInTheDocument()
    })

    it('renders AuthGuard exactly once per render', () => {
        const { rerender } = render(<Page />)
        expect(mockAuthGuardRender).toHaveBeenCalledTimes(1)

        rerender(<Page />)
        expect(mockAuthGuardRender).toHaveBeenCalledTimes(2)
    })
})
