import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Page from '../../../src/app/schema/page'

const mockSchemaPageRender = vi.fn()
const mockAuthGuardRender = vi.fn()
const mockAuthGuardProps = vi.fn()

vi.mock('@/components/AuthGuard', () => ({
    default: ({ children }: { children: React.ReactNode }) => {
        mockAuthGuardRender()
        mockAuthGuardProps(children)
        return <div data-testid="auth-guard">{children}</div>
    }
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
    })

    it('renders SchemaPage when access token exists', async () => {
        render(<Page />)
        expect(screen.getByTestId('auth-guard')).toBeInTheDocument()
        expect(screen.getByTestId('schema-page')).toBeInTheDocument()
        expect(screen.getByText('SchemaPage Component')).toBeInTheDocument()
    })

    it('wraps SchemaPage with AuthGuard', () => {
        render(<Page />)
        expect(mockAuthGuardProps).toHaveBeenCalled()
        expect(screen.getByTestId('schema-page')).toBeInTheDocument()
    })

    it('calls SchemaPage and AuthGuard exactly once per render', () => {
        const { rerender } = render(<Page />)
        expect(mockSchemaPageRender).toHaveBeenCalledTimes(1)
        expect(mockAuthGuardRender).toHaveBeenCalledTimes(1)

        rerender(<Page />)
        expect(mockSchemaPageRender).toHaveBeenCalledTimes(2)
        expect(mockAuthGuardRender).toHaveBeenCalledTimes(2)
    })
})
