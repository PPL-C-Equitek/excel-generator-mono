/**
 * [REFACTOR] ConvertPage rendering tests
 *
 * Setelah refactor, ConvertPage adalah pure presentational component.
 * Test ini hanya memverifikasi RENDERING berdasarkan state yang dikembalikan
 * oleh useConvertFlow — logic bisnis diuji terpisah di useConvertFlow.test.ts.
 *
 * F.I.R.S.T:
 * - Fast: useConvertFlow di-mock, tidak ada async/network
 * - Independent: setiap describe kelompok mengeset state hook-nya sendiri
 * - Repeatable: mock deterministik via vi.fn()
 * - Self-validating: assertions jelas pada elemen DOM
 * - Timely: ditulis bersamaan implementasi refactor
 */

import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { OutputFile } from '../../../src/hooks/useConvertFlow'
import ConvertPage from '../../../src/app/convert/ConvertPage'

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

vi.mock('../../../src/components/Sidebar', () => ({
    default: () => <div data-testid="sidebar" />,
}))

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
        const file = new File(['content'], 'report.pdf', { type: 'application/pdf' })
        return (
            <div data-testid="upload-zone">
                <button data-testid="upload-btn" onClick={() => onFileSelect?.(file)}>
                    Upload File
                </button>
                {footerContent}
                {validationError && <div role="alert">{validationError}</div>}
                {resultContent}
            </div>
        )
    },
}))

// Centralized mock return value — set per describe block
const mockHandleFileSelect = vi.fn()
const mockHandleCsvDownload = vi.fn()
const mockHandleExcelDownload = vi.fn()
const mockHookReturn = {
    isConverting: false,
    isValidating: false,
    isGenerating: false,
    errorPhase: null as 'idle' | 'validating' | 'generating' | null,
    isExcelDownloading: false,
    canDownloadCsv: false,
    canDownloadExcel: false,
    error: null as string | null,
    excelError: null as string | null,
    excelSuccessMessage: null as string | null,
    outputFile: null as OutputFile | null,
    thinkingLog: null as string | null,
    reasoningSteps: [] as string[],
    csvMetadata: null as { file_id: string } | null,
    handleFileSelect: mockHandleFileSelect,
    resetConversionState: vi.fn(),
    handleCsvDownload: mockHandleCsvDownload,
    handleExcelDownload: mockHandleExcelDownload,
    llmService: { getDownloadUrl: vi.fn() }
}

vi.mock('../../../src/hooks/useConvertFlow', () => ({
    useConvertFlow: () => mockHookReturn,
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const sampleOutput: OutputFile = {
    filename: 'report.pdf',
    format: 'pdf',
    size: 20480,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ConvertPage — rendering tests (post-refactor)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        // Reset hook state to idle
        mockHookReturn.isConverting = false
        mockHookReturn.isValidating = false
        mockHookReturn.isGenerating = false
        mockHookReturn.errorPhase = null
        mockHookReturn.isExcelDownloading = false
        mockHookReturn.canDownloadCsv = false
        mockHookReturn.canDownloadExcel = false
        mockHookReturn.error = null
        mockHookReturn.excelError = null
        mockHookReturn.excelSuccessMessage = null
        mockHookReturn.outputFile = null
        mockHookReturn.thinkingLog = null
        mockHookReturn.reasoningSteps = []
        mockHookReturn.csvMetadata = null
        mockHookReturn.handleCsvDownload = mockHandleCsvDownload
        mockHookReturn.handleExcelDownload = mockHandleExcelDownload
        mockHookReturn.llmService = { getDownloadUrl: vi.fn() }
    })

    // -----------------------------------------------------------------------
    // Static layout
    // -----------------------------------------------------------------------
    describe('static layout', () => {
        it('renders schema selector content in the convert chat shell', () => {
            render(<ConvertPage />)
            expect(screen.getByText('Choose A Schema')).toBeInTheDocument()
            expect(screen.getByText(/Use a saved schema/i)).toBeInTheDocument()
        })

        it('renders Sidebar and UploadZone components', () => {
            render(<ConvertPage />)
            expect(screen.getByTestId('sidebar')).toBeInTheDocument()
            expect(screen.getByTestId('upload-zone')).toBeInTheDocument()
        })

        it('uses semantic main content without the removed workspace heading', () => {
            const { container } = render(<ConvertPage />)
            expect(container.querySelector('main')).toBeInTheDocument()
            expect(container.querySelectorAll('h1')).toHaveLength(0)
        })
    })

    // -----------------------------------------------------------------------
    // Idle state — nothing extra shown
    // -----------------------------------------------------------------------
    describe('idle state (no conversion started)', () => {
        it('does not show loading indicator', () => {
            render(<ConvertPage />)
            expect(screen.queryByRole('status')).not.toBeInTheDocument()
        })

        it('does not show error alert', () => {
            render(<ConvertPage />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        })

        it('does not show output download button', () => {
            render(<ConvertPage />)
            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Loading state
    // -----------------------------------------------------------------------
    describe('loading state (isGenerating=true)', () => {
        it('shows reasoning steps loading UI', () => {
            mockHookReturn.isConverting = true
            mockHookReturn.isGenerating = true
            render(<ConvertPage />)
            expect(screen.getByTestId('reasoning-steps')).toBeInTheDocument()
        })

        it('shows thinking process loading text', () => {
            mockHookReturn.isConverting = true
            mockHookReturn.isGenerating = true
            render(<ConvertPage />)
            expect(screen.getByText('Loading thinking process...')).toBeInTheDocument()
        })

        it('does not show error or output while loading', () => {
            mockHookReturn.isConverting = true
            mockHookReturn.isGenerating = true
            render(<ConvertPage />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Error state
    // -----------------------------------------------------------------------
    describe('error state (error set)', () => {
        it('shows role="alert" with error message', () => {
            mockHookReturn.error = 'Upload failed'
            mockHookReturn.errorPhase = 'generating'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('Upload failed')).toBeInTheDocument()
        })

        it('shows role="alert" for schema validation error', () => {
            mockHookReturn.error = 'The server returned an invalid upload response.'
            mockHookReturn.errorPhase = 'validating'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('The server returned an invalid upload response.')).toBeInTheDocument()
        })

        it('shows role="alert" for LLM conversion error', () => {
            mockHookReturn.error = 'LLM quota exceeded'
            mockHookReturn.errorPhase = 'generating'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('LLM quota exceeded')).toBeInTheDocument()
        })

        it('does not show output download button when error is set', () => {
            mockHookReturn.error = 'Upload failed'
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.queryByTestId('download-csv-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Success state
    // -----------------------------------------------------------------------
    describe('success state (outputFile set, no error)', () => {
        it('shows output filename', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.getByText('report.pdf')).toBeInTheDocument()
        })

        it('shows the final thinking log when output is ready', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.thinkingLog = 'Final reasoning summary.'

            render(<ConvertPage />)

            expect(screen.getByText('Thinking log')).toBeInTheDocument()
            expect(screen.getByText('Final reasoning summary.')).toBeInTheDocument()
        })

        it('completes reasoning playback when the thinking log is absent', async () => {
            const setTimeoutSpy = vi
                .spyOn(globalThis, 'setTimeout')
                .mockImplementation((handler: TimerHandler) => {
                    if (typeof handler === 'function') {
                        handler()
                        handler()
                        handler()
                    }

                    return 1 as unknown as ReturnType<typeof globalThis.setTimeout>
                })
            const clearTimeoutSpy = vi
                .spyOn(globalThis, 'clearTimeout')
                .mockImplementation(() => undefined)

            try {
                mockHookReturn.outputFile = sampleOutput
                mockHookReturn.reasoningSteps = ['Reviewed the uploaded file.']
                mockHookReturn.thinkingLog = null

                render(<ConvertPage />)

                expect(screen.getByText('Your file is ready.')).toBeInTheDocument()
                expect(screen.queryByText('Thinking log')).not.toBeInTheDocument()
            } finally {
                setTimeoutSpy.mockRestore()
                clearTimeoutSpy.mockRestore()
            }
        })

        it('reveals reasoning steps before the final thinking log', async () => {
            vi.useFakeTimers()

            try {
                mockHookReturn.outputFile = sampleOutput
                mockHookReturn.reasoningSteps = [
                    'Reviewed the uploaded file.',
                    'Mapped the output columns.',
                ]
                mockHookReturn.thinkingLog = 'Final reasoning summary.'

                render(<ConvertPage />)

                await act(async () => {
                    vi.advanceTimersByTime(250)
                })

                expect(screen.getByText('Reviewed the uploaded file.')).toBeInTheDocument()
                expect(screen.getByText('Loading thinking process...')).toBeInTheDocument()
                expect(screen.queryByText('Thinking log')).not.toBeInTheDocument()
            } finally {
                vi.useRealTimers()
            }
        })

        it('keeps reasoning steps available in a dropdown after playback completes', async () => {
            const setTimeoutSpy = vi
                .spyOn(globalThis, 'setTimeout')
                .mockImplementation((handler: TimerHandler) => {
                    if (typeof handler === 'function') {
                        handler()
                        handler()
                        handler()
                    }

                    return 1 as unknown as ReturnType<typeof globalThis.setTimeout>
                })
            const clearTimeoutSpy = vi
                .spyOn(globalThis, 'clearTimeout')
                .mockImplementation(() => undefined)
            const user = userEvent.setup()

            try {
                mockHookReturn.outputFile = sampleOutput
                mockHookReturn.reasoningSteps = ['Reviewed the uploaded file.']
                mockHookReturn.thinkingLog = 'Final reasoning summary.'

                render(<ConvertPage />)

                expect(screen.getByText('Thinking log')).toBeInTheDocument()
                expect(screen.queryByText('Reviewed the uploaded file.')).not.toBeInTheDocument()

                await user.click(screen.getByRole('button', { name: /reasoning steps/i }))

                expect(screen.getByText('Reviewed the uploaded file.')).toBeInTheDocument()
            } finally {
                setTimeoutSpy.mockRestore()
                clearTimeoutSpy.mockRestore()
            }
        })

        it('shows output format', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            const pdfMatches = screen.getAllByText(/pdf/i)
            expect(pdfMatches.length).toBeGreaterThan(0)
        })

        it('shows file size in KB', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.getByTestId('file-size')).toHaveTextContent('20 KB')
        })

        it('shows Download CSV label', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.canDownloadCsv = true
            render(<ConvertPage />)
            expect(screen.getByText('Download CSV')).toBeInTheDocument()
        })

        it('shows Download CSV button when csv download is available even before metadata exists', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.canDownloadCsv = true
            mockHookReturn.csvMetadata = null

            render(<ConvertPage />)

            expect(screen.getByTestId('download-csv-btn')).toBeInTheDocument()
            expect(screen.getByTestId('download-csv-btn')).toBeEnabled()
        })

        it('shows Download Excel button when excel is available', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            render(<ConvertPage />)

            expect(screen.getByTestId('download-excel-btn')).toBeInTheDocument()
            expect(screen.getByText('Download Excel')).toBeInTheDocument()
        })

        it('does not show Download Excel button when excel is not available', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = false
            render(<ConvertPage />)

            expect(screen.queryByTestId('download-excel-btn')).not.toBeInTheDocument()
        })

        it('triggers handleExcelDownload when Download Excel is clicked', async () => {
            const user = userEvent.setup()
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true

            render(<ConvertPage />)
            await user.click(screen.getByTestId('download-excel-btn'))

            expect(mockHandleExcelDownload).toHaveBeenCalledTimes(1)
        })

        it('disables Download Excel and shows loading text while excel download is active', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            mockHookReturn.isExcelDownloading = true

            render(<ConvertPage />)

            const excelButton = screen.getByTestId('download-excel-btn')
            expect(excelButton).toBeDisabled()
            expect(screen.getByText(/downloading excel/i)).toBeInTheDocument()
        })

        it('shows excel error feedback when excel download fails', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            mockHookReturn.excelError = 'Failed to export'

            render(<ConvertPage />)

            expect(screen.getByText('Failed to export')).toBeInTheDocument()
        })

        it('shows success feedback when excel download succeeds', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            mockHookReturn.excelSuccessMessage = 'Successfully downloaded'

            render(<ConvertPage />)

            expect(screen.getByText('Successfully downloaded')).toBeInTheDocument()
        })

        it('shows Retry action when excel download fails', () => {
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            mockHookReturn.excelError = 'Failed to export'

            render(<ConvertPage />)

            expect(screen.getByTestId('retry-excel-btn')).toBeInTheDocument()
            expect(screen.getByText('Retry')).toBeInTheDocument()
        })

        it('triggers handleExcelDownload when Retry is clicked', async () => {
            const user = userEvent.setup()
            mockHookReturn.outputFile = sampleOutput
            mockHookReturn.csvMetadata = { file_id: 'csv_123' }
            mockHookReturn.canDownloadExcel = true
            mockHookReturn.excelError = 'Failed to export'

            render(<ConvertPage />)
            await user.click(screen.getByTestId('retry-excel-btn'))

            expect(mockHandleExcelDownload).toHaveBeenCalledTimes(1)
        })

        it('delegates CSV download to the hook instead of constructing the URL in the page', async () => {
            const user = userEvent.setup()

            mockHookReturn.outputFile = { filename: 'report.pdf', format: 'pdf', size: 20480 }
            mockHookReturn.canDownloadCsv = true
            mockHookReturn.csvMetadata = null

            render(<ConvertPage />)
            await user.click(screen.getByTestId('download-csv-btn'))

            expect(mockHandleCsvDownload).toHaveBeenCalledTimes(1)
            expect(mockHookReturn.llmService.getDownloadUrl).not.toHaveBeenCalled()
        })
    })

    // -----------------------------------------------------------------------
    // Hook wiring
    // -----------------------------------------------------------------------
    describe('hook wiring', () => {
        it('passes handleFileSelect from hook to UploadZone', async () => {
            const user = userEvent.setup()
            render(<ConvertPage />)
            await user.click(screen.getByTestId('upload-btn'))
            expect(mockHandleFileSelect).toHaveBeenCalledTimes(1)
            expect(mockHandleFileSelect).toHaveBeenCalledWith(expect.any(File), null, null)
        })
    })
})
