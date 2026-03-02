import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import Page from '../../../src/app/convert/page'

// Mock ConvertPage component with advanced stub
const mockConvertPageRender = vi.fn()

vi.mock('../../../src/app/convert/ConvertPage', () => ({
    default: () => {
        mockConvertPageRender()
        return (
            <div data-testid="convert-page">
                <h1>ConvertPage Component</h1>
                <p data-testid="component-type">Mocked Component</p>
            </div>
        )
    }
}))

describe('Convert Page Wrapper', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockConvertPageRender.mockClear()
    })

    afterEach(() => {
        vi.resetAllMocks()
    })

    describe('Component Rendering', () => {
        it('renders without crashing', () => {
            const { container } = render(<Page />)
            expect(container).toBeTruthy()
        })

        it('renders ConvertPage component', () => {
            render(<Page />)
            expect(screen.getByText('ConvertPage Component')).toBeInTheDocument()
        })

        it('displays ConvertPage content correctly', () => {
            render(<Page />)
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
            expect(screen.getByTestId('component-type')).toHaveTextContent('Mocked Component')
        })
    })

    describe('Component Type and Behavior', () => {
        it('exports default function', () => {
            expect(Page).toBeDefined()
            expect(typeof Page).toBe('function')
        })

        it('is a valid React component', () => {
            expect(() => render(<Page />)).not.toThrow()
        })

        it('calls ConvertPage exactly once on render', () => {
            render(<Page />)
            expect(mockConvertPageRender).toHaveBeenCalledTimes(1)
        })

        it('calls ConvertPage on each render', () => {
            const { rerender } = render(<Page />)
            expect(mockConvertPageRender).toHaveBeenCalledTimes(1)

            rerender(<Page />)
            expect(mockConvertPageRender).toHaveBeenCalledTimes(2)
        })
    })

    describe('Component Integration', () => {
        it('acts as a thin wrapper around ConvertPage', () => {
            const { container } = render(<Page />)
            const convertPage = screen.getByTestId('convert-page')

            expect(container.firstChild).toBe(convertPage)
        })

        it('does not add additional wrapper elements', () => {
            const { container } = render(<Page />)
            const children = Array.from(container.children)

            expect(children).toHaveLength(1)
            expect(children[0]).toHaveAttribute('data-testid', 'convert-page')
        })

        it('passes through React rendering context', () => {
            const result = render(<Page />)
            expect(result).toBeDefined()
            expect(result.container).toBeInstanceOf(HTMLElement)
        })
    })

    describe('Component Lifecycle', () => {
        it('can be unmounted without errors', () => {
            const { unmount } = render(<Page />)
            expect(() => unmount()).not.toThrow()
        })

        it('can be rendered multiple times', () => {
            const { unmount: unmount1 } = render(<Page />)
            const { unmount: unmount2 } = render(<Page />)

            expect(mockConvertPageRender).toHaveBeenCalledTimes(2)

            expect(() => {
                unmount1()
                unmount2()
            }).not.toThrow()
        })

        it('maintains consistent behavior across renders', () => {
            const { rerender, container } = render(<Page />)
            const firstRender = container.innerHTML

            rerender(<Page />)
            const secondRender = container.innerHTML

            expect(firstRender).toBe(secondRender)
        })
    })

    describe('Edge Cases', () => {
        it('handles rapid re-renders', () => {
            const { rerender } = render(<Page />)

            for (let i = 0; i < 10; i++) {
                rerender(<Page />)
            }

            expect(mockConvertPageRender).toHaveBeenCalledTimes(11)
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
        })

        it('maintains component identity', () => {
            render(<Page />)
            const component1 = screen.getByTestId('convert-page')

            expect(component1).toBeInTheDocument()
            expect(component1.tagName).toBe('DIV')
        })
    })

    describe('Component Isolation', () => {
        it('does not interfere with other test cases', () => {
            render(<Page />)
            expect(mockConvertPageRender).toHaveBeenCalledTimes(1)
        })

        it('renders independently in different test contexts', () => {
            const firstRender = render(<Page />)
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
            firstRender.unmount()

            const secondRender = render(<Page />)
            expect(screen.getByTestId('convert-page')).toBeInTheDocument()
            secondRender.unmount()

            expect(mockConvertPageRender).toHaveBeenCalledTimes(2)
        })
    })

    describe('TypeScript and Type Safety', () => {
        it('is properly typed as a React component', () => {
            const PageComponent = Page
            expect(typeof PageComponent).toBe('function')
        })

        it('returns valid React element', () => {
            const result = Page()
            expect(result).toBeDefined()
            expect(result).toHaveProperty('type')
            expect(result).toHaveProperty('props')
        })
    })
})
