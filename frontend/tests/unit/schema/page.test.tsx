import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import Page from '../../../src/app/schema/page'

const mockSchemaPageRender = vi.fn()

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

describe('Schema Page Wrapper', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSchemaPageRender.mockClear()
    })

    afterEach(() => {
        vi.resetAllMocks()
    })

    it('renders SchemaPage component', () => {
        render(<Page />)
        expect(screen.getByTestId('schema-page')).toBeInTheDocument()
        expect(screen.getByText('SchemaPage Component')).toBeInTheDocument()
    })

    it('acts as a thin wrapper around SchemaPage', () => {
        const { container } = render(<Page />)
        expect(container.firstChild).toBe(screen.getByTestId('schema-page'))
    })

    it('calls SchemaPage exactly once per render', () => {
        const { rerender } = render(<Page />)
        expect(mockSchemaPageRender).toHaveBeenCalledTimes(1)

        rerender(<Page />)
        expect(mockSchemaPageRender).toHaveBeenCalledTimes(2)
    })
})
