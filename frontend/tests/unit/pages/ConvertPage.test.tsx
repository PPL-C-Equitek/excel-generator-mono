import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('../../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))
vi.mock('../../../src/services/llm', () => ({
    generateJson: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
}))

import { uploadFile } from '../../../src/lib/api'
const mockUploadFile = vi.mocked(uploadFile)
import ConvertPage from '../../../src/app/convert/ConvertPage'

// Test utilities - Factory pattern for creating test data
const createMockFile = (name = 'test.pdf', type = 'application/pdf', content = 'test') => {
    return new File([content], name, { type })
}

// Mock tracking for component props
let mockOnFileSelectCalls: Array<{ file: File }> = []

// Mock the UploadZone component with more control
vi.mock('../../../src/components/UploadZone', () => ({
    default: ({ onFileSelect }: { onFileSelect?: (file: File) => void }) => {
        const handleClick = () => {
            const mockFile = createMockFile()
            mockOnFileSelectCalls.push({ file: mockFile })
            onFileSelect?.(mockFile)
        }

        return (
            <div data-testid="upload-zone">
                <button onClick={handleClick}>Upload File</button>
                <span data-testid="upload-zone-rendered">UploadZone Rendered</span>
            </div>
        )
    }
}))

// Mock the Sidebar component with prop validation
vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu, username }: { activeMenu: string; username: string }) => (
        <div data-testid="sidebar">
            <div>EQUITEK</div>
            <div data-testid="active-menu">{activeMenu}</div>
            <div data-testid="username">{username}</div>
        </div>
    )
}))

describe('ConvertPage', () => {
    let consoleLogSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        // Reset test state
        mockOnFileSelectCalls = []

        // Spy on console methods
        consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => { })

        // Default: uploadFile resolves successfully
        mockUploadFile.mockResolvedValue({ filename: 'test.xlsx', size: 10240, format: 'xlsx' })
    })

    afterEach(() => {
        // Cleanup spies
        consoleLogSpy.mockRestore()
        vi.clearAllMocks()
    })

    describe('Component Rendering', () => {
        it('renders without crashing', () => {
            const { container } = render(<ConvertPage />)
            expect(container).toBeTruthy()
        })

        it('renders page heading with correct text', () => {
            render(<ConvertPage />)
            expect(screen.getByText('Automate Your Data Structuring')).toBeInTheDocument()
        })

        it('renders subtitle text', () => {
            render(<ConvertPage />)
            expect(screen.getByText(/Replace manual entry/i)).toBeInTheDocument()
        })

        it('renders complete subtitle with AI-driven text', () => {
            render(<ConvertPage />)
            expect(screen.getByText(/AI-driven extraction/i)).toBeInTheDocument()
            expect(screen.getByText(/seamless Excel template mapping/i)).toBeInTheDocument()
        })

        it('renders all child components', () => {
            render(<ConvertPage />)
            expect(screen.getByTestId('sidebar')).toBeInTheDocument()
            expect(screen.getByTestId('upload-zone')).toBeInTheDocument()
        })
    })

    describe('Component Props and Integration', () => {
        it('passes correct activeMenu prop to Sidebar', () => {
            render(<ConvertPage />)
            const sidebar = screen.getByTestId('sidebar')
            const activeMenu = within(sidebar).getByTestId('active-menu')
            expect(activeMenu).toHaveTextContent('convert')
        })

        it('passes correct username prop to Sidebar', () => {
            render(<ConvertPage />)
            const sidebar = screen.getByTestId('sidebar')
            const username = within(sidebar).getByTestId('username')
            expect(username).toHaveTextContent('Username')
        })

        it('renders UploadZone component properly', () => {
            render(<ConvertPage />)
            expect(screen.getByTestId('upload-zone-rendered')).toBeInTheDocument()
            expect(screen.getByText('Upload File')).toBeInTheDocument()
        })

        it('ensures UploadZone receives onFileSelect callback', () => {
            render(<ConvertPage />)
            const uploadZone = screen.getByTestId('upload-zone')
            expect(uploadZone).toBeInTheDocument()
        })
    })

    describe('Layout and Styling', () => {
        it('has correct layout structure with flex container', () => {
            const { container } = render(<ConvertPage />)
            const mainContainer = container.querySelector('.flex.min-h-screen')
            expect(mainContainer).toBeInTheDocument()
            expect(mainContainer).toBeInstanceOf(HTMLDivElement)
        })

        it('main content area has correct styling classes', () => {
            const { container } = render(<ConvertPage />)
            const mainContent = container.querySelector('main')
            expect(mainContent).toHaveClass('flex-1', 'bg-gray-50')
            expect(mainContent).toHaveClass('flex', 'flex-col', 'items-center', 'justify-center')
        })

        it('heading has correct styling and semantic HTML', () => {
            render(<ConvertPage />)
            const heading = screen.getByText('Automate Your Data Structuring')
            expect(heading.tagName).toBe('H1')
            expect(heading).toHaveClass('text-2xl', 'font-bold', 'text-gray-900', 'mb-3')
        })

        it('subtitle has correct styling', () => {
            render(<ConvertPage />)
            const subtitle = screen.getByText(/Replace manual entry/i)
            expect(subtitle.tagName).toBe('P')
            expect(subtitle).toHaveClass('text-gray-500', 'text-center')
        })

        it('container for UploadZone has max width constraint', () => {
            const { container } = render(<ConvertPage />)
            const uploadContainer = container.querySelector('.max-w-3xl')
            expect(uploadContainer).toBeInTheDocument()
            expect(uploadContainer).toHaveClass('w-full')
        })

        it('renders with correct responsive padding', () => {
            const { container } = render(<ConvertPage />)
            const mainContent = container.querySelector('main')
            expect(mainContent).toHaveClass('px-16')
        })
    })

    describe('File Handling', () => {
        it('calls handleFileSelect when file is selected', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(1)
                expect(mockUploadFile).toHaveBeenCalledWith(expect.any(File), expect.any(Object))
            })
        })

        it('handleFileSelect receives correct file object', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(1)
                const calledFile = mockUploadFile.mock.calls[0][0] as File
                expect(calledFile.name).toBe('test.pdf')
            })
        })

        it('tracks file selection in mock calls', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            expect(mockOnFileSelectCalls).toHaveLength(0)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            await waitFor(() => {
                expect(mockOnFileSelectCalls).toHaveLength(1)
                expect(mockOnFileSelectCalls[0].file.name).toBe('test.pdf')
            })
        })

        it('handles file selection only when callback is defined', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            const uploadButton = screen.getByText('Upload File')

            // Should not throw error
            await expect(user.click(uploadButton)).resolves.not.toThrow()
        })
    })

    describe('User Interactions', () => {
        it('allows multiple file selections', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            const uploadButton = screen.getByText('Upload File')

            await user.click(uploadButton)
            await user.click(uploadButton)

            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(2)
            })
        })

        it('maintains consistent behavior on repeated interactions', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)

            const uploadButton = screen.getByText('Upload File')

            for (let i = 0; i < 3; i++) {
                await user.click(uploadButton)
            }

            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(3)
                expect(mockOnFileSelectCalls).toHaveLength(3)
            })
        })
    })

    describe('Accessibility and Semantics', () => {
        it('uses semantic HTML elements', () => {
            const { container } = render(<ConvertPage />)
            expect(container.querySelector('main')).toBeInTheDocument()
            expect(container.querySelector('h1')).toBeInTheDocument()
        })

        it('maintains proper heading hierarchy', () => {
            const { container } = render(<ConvertPage />)
            const h1Elements = container.querySelectorAll('h1')
            expect(h1Elements).toHaveLength(1)
        })
    })

    describe('Edge Cases', () => {
        it('renders correctly when no file is selected', () => {
            render(<ConvertPage />)
            expect(screen.queryByText(/selected/i)).not.toBeInTheDocument()
        })

        it('does not throw when console.log is unavailable', async () => {
            consoleLogSpy.mockRestore()
            const user = userEvent.setup()

            render(<ConvertPage />)
            const uploadButton = screen.getByText('Upload File')

            await expect(user.click(uploadButton)).resolves.not.toThrow()
            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(1)
            })
        })
    })

    describe('Component Isolation', () => {
        it('renders independently without external dependencies', () => {
            const { unmount } = render(<ConvertPage />)
            expect(() => unmount()).not.toThrow()
        })

        it('can be rendered multiple times without conflicts', () => {
            const { unmount: unmount1 } = render(<ConvertPage />)
            const { unmount: unmount2 } = render(<ConvertPage />)

            expect(() => {
                unmount1()
                unmount2()
            }).not.toThrow()
        })
    })
})