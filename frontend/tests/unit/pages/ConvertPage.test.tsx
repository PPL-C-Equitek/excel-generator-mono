import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ILLMService } from '../../../src/lib/ILLMService'

vi.mock('../../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))
vi.mock('../../../src/services/llm', () => ({
    generateJson: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
    exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_777' }),
    downloadCsvFile: vi.fn().mockResolvedValue(undefined),
    downloadSessionOutputCsvFile: vi.fn().mockResolvedValue(undefined),
    exportToExcel: vi.fn().mockResolvedValue({
        file_id: 'xlsx_777',
        file_name: 'export_777.xlsx',
        artifact_type: 'xlsx',
    }),
    downloadExcelFile: vi.fn().mockResolvedValue(undefined),
    downloadSessionOutputExcelFile: vi.fn().mockResolvedValue(undefined),
    getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_777/download?filename=test.csv'),
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
    default: ({
        onFileSelect,
        footerContent,
        resultContent,
        validationError,
    }: {
        onFileSelect?: (file: File) => void
        footerContent?: ReactNode
        resultContent?: ReactNode
        validationError?: string | null
    }) => {
        const handleClick = () => {
            const mockFile = createMockFile()
            mockOnFileSelectCalls.push({ file: mockFile })
            onFileSelect?.(mockFile)
        }

        return (
            <div data-testid="upload-zone">
                <button onClick={handleClick}>Upload File</button>
                <span data-testid="upload-zone-rendered">UploadZone Rendered</span>
                {footerContent}
                {validationError && <div role="alert">{validationError}</div>}
                {resultContent}
            </div>
        )
    }
}))

// Mock the Sidebar component with active menu validation
vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu }: { activeMenu: string }) => (
        <div data-testid="sidebar">
            <div>EQUITEK</div>
            <div data-testid="active-menu">{activeMenu}</div>
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
        vi.unstubAllEnvs()
    })

    describe('Component Rendering', () => {
        it('renders without crashing', () => {
            const { container } = render(<ConvertPage />)
            expect(container).toBeTruthy()
        })

        it('renders schema selector heading in the simplified convert page', () => {
            render(<ConvertPage />)
            expect(screen.getByText('Choose A Schema')).toBeInTheDocument()
        })

        it('renders schema selector helper text', () => {
            render(<ConvertPage />)
            expect(screen.getByText(/Use a saved schema/i)).toBeInTheDocument()
        })

        it('renders schema builder entry point', () => {
            render(<ConvertPage />)
            expect(screen.getByText('Open Schema Builder')).toBeInTheDocument()
        })

        it('renders all child components', () => {
            render(<ConvertPage />)
            expect(screen.getByTestId('sidebar')).toBeInTheDocument()
            expect(screen.getByTestId('upload-zone')).toBeInTheDocument()
            expect(screen.getByText('Choose A Schema')).toBeInTheDocument()
        })
    })

    describe('Component Props and Integration', () => {
        it('passes correct activeMenu prop to Sidebar', () => {
            render(<ConvertPage />)
            const sidebar = screen.getByTestId('sidebar')
            const activeMenu = within(sidebar).getByTestId('active-menu')
            expect(activeMenu).toHaveTextContent('convert')
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
            expect(mainContent).toHaveClass('ml-56', 'flex', 'min-h-screen', 'flex-1', 'bg-gray-50')
        })

        it('schema selector heading has accessible heading semantics', () => {
            render(<ConvertPage />)
            const heading = screen.getByText('Choose A Schema')
            expect(heading.tagName).toBe('H2')
            expect(heading).toHaveClass('text-lg', 'font-semibold', 'text-gray-900')
        })

        it('schema selector helper text has muted styling', () => {
            render(<ConvertPage />)
            const subtitle = screen.getByText(/Use a saved schema/i)
            expect(subtitle.tagName).toBe('P')
            expect(subtitle).toHaveClass('text-sm', 'text-gray-500')
        })

        it('container for UploadZone spans available chat width', () => {
            const { container } = render(<ConvertPage />)
            const uploadContainer = container.querySelector('main > div')
            expect(uploadContainer).toBeInTheDocument()
            expect(uploadContainer).toHaveClass('w-full')
        })

        it('renders without legacy responsive padding on main', () => {
            const { container } = render(<ConvertPage />)
            const mainContent = container.querySelector('main')
            expect(mainContent).not.toHaveClass('px-16')
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
            expect(container.querySelector('h2')).toBeInTheDocument()
        })

        it('maintains proper heading hierarchy', () => {
            const { container } = render(<ConvertPage />)
            const h1Elements = container.querySelectorAll('h1')
            expect(h1Elements).toHaveLength(0)
            expect(container.querySelectorAll('h2').length).toBeGreaterThan(0)
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

    describe('Export to CSV Integration UI', () => {
        it('does not display Download CSV when initial mount or csvMetadata is null', () => {
            render(<ConvertPage />)
            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
        })

        it('does not display Download CSV button during conversion before output is ready', async () => {
            const user = userEvent.setup()
            const mockService = {
                generate: vi.fn().mockImplementationOnce(
                    () => new Promise(() => { })
                ),
                exportToCsv: vi.fn(),
                downloadCsvFile: vi.fn(),
                getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_pending/download?filename=test.csv')
            }

            render(<ConvertPage llmService={mockService as unknown as ILLMService} />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
            expect(mockService.exportToCsv).not.toHaveBeenCalled()
        })

        it('shows enabled Download CSV button after successful conversion', async () => {
            const user = userEvent.setup()

            const mockService = {
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
                exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_999' }),
                downloadCsvFile: vi.fn().mockResolvedValue(undefined),
                getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_999/download?filename=test.csv')
            }

            render(<ConvertPage llmService={mockService as unknown as ILLMService} />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            await waitFor(() => {
                const csvBtn = screen.getByTestId('download-csv-btn')
                expect(csvBtn).toBeInTheDocument()
                expect(csvBtn).not.toBeDisabled()
            })
        })

        it('does not export CSV until Download CSV is clicked', async () => {
            const user = userEvent.setup()
            const mockService = {
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
                exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_999' }),
                downloadCsvFile: vi.fn().mockResolvedValue(undefined),
                getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_999/download?filename=test.csv')
            }

            render(<ConvertPage llmService={mockService as unknown as ILLMService} />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            const csvBtn = await screen.findByTestId('download-csv-btn')
            expect(mockService.exportToCsv).not.toHaveBeenCalled()

            await user.click(csvBtn)

            expect(mockService.exportToCsv).toHaveBeenCalledTimes(1)
            expect(mockService.exportToCsv).toHaveBeenCalledWith(
                {
                    document_info: {
                        source_type: 'Excel',
                        filename: 'test.xlsx',
                    },
                    summary: {
                        total_tables: 1,
                        total_rows: 1,
                        total_columns: 1,
                    },
                    content_data: [
                        {
                            table_name: 'Sheet1',
                            headers: ['status'],
                            rows: [{ status: 'ok' }],
                        },
                    ],
                },
                expect.any(AbortSignal)
            )
            expect(mockService.getDownloadUrl).not.toHaveBeenCalled()
        })

        it('keeps Download CSV enabled even before csvMetadata exists and starts export on click', async () => {
            const user = userEvent.setup()
            const delayedMockService = {
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
                exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_999' }),
                downloadCsvFile: vi.fn().mockResolvedValue(undefined),
                getDownloadUrl: vi.fn()
            }

            render(<ConvertPage llmService={delayedMockService as unknown as ILLMService} />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            const csvBtn = await screen.findByTestId('download-csv-btn')
            expect(csvBtn).not.toBeDisabled()

            await user.click(csvBtn)

            expect(delayedMockService.exportToCsv).toHaveBeenCalledTimes(1)
        })

        it('shows error message if CSV export fails', async () => {
            const user = userEvent.setup()
            const mockService = {
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
                exportToCsv: vi.fn().mockRejectedValue(new Error('CSV Export Error')),
                downloadCsvFile: vi.fn().mockResolvedValue(undefined),
                getDownloadUrl: vi.fn()
            }

            render(<ConvertPage llmService={mockService as unknown as ILLMService} />)

            const uploadButton = screen.getByText('Upload File')
            await user.click(uploadButton)

            const csvBtn = await screen.findByTestId('download-csv-btn')
            await user.click(csvBtn)

            const alertEl = await screen.findByRole('alert')
            expect(alertEl).toHaveTextContent(/CSV Export Error/i)

            // Buttons block unmounts when there's an error
            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
        })
    })
})
