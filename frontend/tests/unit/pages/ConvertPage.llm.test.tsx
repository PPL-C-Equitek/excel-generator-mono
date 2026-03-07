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

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    default: ({ onFileSelect }: { onFileSelect?: (file: File) => void }) => {
        const file = new File(['content'], 'report.pdf', { type: 'application/pdf' })
        return (
            <div data-testid="upload-zone">
                <button data-testid="upload-btn" onClick={() => onFileSelect?.(file)}>
                    Upload File
                </button>
            </div>
        )
    },
}))

// Centralized mock return value — set per describe block
const mockHandleFileSelect = vi.fn()
const mockHookReturn = {
    isConverting: false,
    error: null as string | null,
    outputFile: null as OutputFile | null,
    handleFileSelect: mockHandleFileSelect,
}

vi.mock('../../../src/hooks/useConvertFlow', () => ({
    useConvertFlow: () => mockHookReturn,
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const sampleOutput: OutputFile = {
    filename: 'report.xlsx',
    format: 'xlsx',
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
        mockHookReturn.error = null
        mockHookReturn.outputFile = null
    })

    // -----------------------------------------------------------------------
    // Static layout
    // -----------------------------------------------------------------------
    describe('static layout', () => {
        it('renders heading and subtitle', () => {
            render(<ConvertPage />)
            expect(screen.getByText('Automate Your Data Structuring')).toBeInTheDocument()
            expect(screen.getByText(/Replace manual entry/i)).toBeInTheDocument()
        })

        it('renders Sidebar and UploadZone components', () => {
            render(<ConvertPage />)
            expect(screen.getByTestId('sidebar')).toBeInTheDocument()
            expect(screen.getByTestId('upload-zone')).toBeInTheDocument()
        })

        it('uses semantic HTML with single h1', () => {
            const { container } = render(<ConvertPage />)
            expect(container.querySelector('h1')).toBeInTheDocument()
            expect(container.querySelectorAll('h1')).toHaveLength(1)
            expect(container.querySelector('main')).toBeInTheDocument()
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

        it('does not show download button', () => {
            render(<ConvertPage />)
            expect(screen.queryByTestId('download-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Loading state
    // -----------------------------------------------------------------------
    describe('loading state (isConverting=true)', () => {
        it('shows loading indicator with role="status"', () => {
            mockHookReturn.isConverting = true
            render(<ConvertPage />)
            expect(screen.getByRole('status')).toBeInTheDocument()
        })

        it('shows "Converting..." text', () => {
            mockHookReturn.isConverting = true
            render(<ConvertPage />)
            expect(screen.getByText(/converting/i)).toBeInTheDocument()
        })

        it('does not show error or output while loading', () => {
            mockHookReturn.isConverting = true
            render(<ConvertPage />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
            expect(screen.queryByTestId('download-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Error state
    // -----------------------------------------------------------------------
    describe('error state (error set)', () => {
        it('shows role="alert" with error message', () => {
            mockHookReturn.error = 'Upload failed'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('Upload failed')).toBeInTheDocument()
        })

        it('shows role="alert" for schema validation error', () => {
            mockHookReturn.error = 'Respons upload tidak valid'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('Respons upload tidak valid')).toBeInTheDocument()
        })

        it('shows role="alert" for LLM conversion error', () => {
            mockHookReturn.error = 'LLM quota exceeded'
            render(<ConvertPage />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
            expect(screen.getByText('LLM quota exceeded')).toBeInTheDocument()
        })

        it('does not show download button when error is set', () => {
            mockHookReturn.error = 'Upload failed'
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.queryByTestId('download-btn')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // Success state
    // -----------------------------------------------------------------------
    describe('success state (outputFile set, no error)', () => {
        it('shows output filename', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.getByText('report.xlsx')).toBeInTheDocument()
        })

        it('shows output format', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            const xlsxMatches = screen.getAllByText(/xlsx/i)
            expect(xlsxMatches.length).toBeGreaterThan(0)
        })

        it('shows file size in KB', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.getByTestId('file-size')).toHaveTextContent('20 KB')
        })

        it('shows Download button', () => {
            mockHookReturn.outputFile = sampleOutput
            render(<ConvertPage />)
            expect(screen.getByTestId('download-btn')).toBeInTheDocument()
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
            expect(mockHandleFileSelect).toHaveBeenCalledWith(expect.any(File))
        })
    })
})
