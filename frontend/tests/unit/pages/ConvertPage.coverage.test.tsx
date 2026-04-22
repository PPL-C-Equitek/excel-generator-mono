import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'

const mockUseConvertFlow = vi.fn()

vi.mock('../../../src/hooks/useConvertFlow', () => ({
    useConvertFlow: (...args: unknown[]) => mockUseConvertFlow(...args),
}))

vi.mock('../../../src/components/Sidebar', () => ({
    default: ({ activeMenu }: { activeMenu: string }) => <div data-testid="sidebar">{activeMenu}</div>,
}))

vi.mock('../../../src/components/SchemaSelector', () => ({
    default: ({ onSchemaChange }: { onSchemaChange?: (value: unknown) => void }) => (
        <button
            type="button"
            data-testid="schema-selector"
            onClick={() => onSchemaChange?.({ id: 99 })}
        >
            Schema Selector
        </button>
    ),
}))

vi.mock('../../../src/components/UploadZone', () => ({
    default: ({ onFileSelect, footerContent }: { onFileSelect?: (file: File) => void; footerContent?: ReactNode }) => (
        <div>
            <button
                type="button"
                data-testid="upload-button"
                onClick={() => onFileSelect?.(new File(['x'], 'sample.pdf', { type: 'application/pdf' }))}
            >
                Upload
            </button>
            {footerContent}
        </div>
    ),
}))

vi.mock('../../../src/components/FeedbackMessage', () => ({
    default: ({ message }: { message: string }) => <p>{message}</p>,
}))

import ConvertPage from '../../../src/app/convert/ConvertPage'

const baseFlowState = () => ({
    isConverting: false,
    isExcelDownloading: false,
    canDownloadCsv: false,
    canDownloadExcel: true,
    error: null,
    excelError: null,
    excelSuccessMessage: null,
    outputFile: {
        filename: 'result.csv',
        format: 'csv',
        size: 2048,
    },
    handleFileSelect: vi.fn().mockResolvedValue(undefined),
    handleCsvDownload: vi.fn().mockResolvedValue(undefined),
    handleExcelDownload: vi.fn().mockResolvedValue(undefined),
})

describe('ConvertPage coverage branches', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('calls handleExcelDownload from primary button and retry button', async () => {
        const flowState = {
            ...baseFlowState(),
            excelError: 'Excel export failed',
        }
        mockUseConvertFlow.mockReturnValue(flowState)

        render(<ConvertPage />)

        fireEvent.click(screen.getByTestId('download-excel-btn'))
        fireEvent.click(screen.getByTestId('retry-excel-btn'))

        expect(flowState.handleExcelDownload).toHaveBeenCalledTimes(2)
    })

    it('shows downloading label when excel download is in progress', () => {
        mockUseConvertFlow.mockReturnValue({
            ...baseFlowState(),
            isExcelDownloading: true,
        })

        render(<ConvertPage />)

        expect(screen.getByTestId('download-excel-btn')).toHaveTextContent('Downloading Excel...')
        expect(screen.getByTestId('download-excel-btn')).toBeDisabled()
    })

    it('renders parent-level errorMessage when hook error is null', () => {
        mockUseConvertFlow.mockReturnValue({
            ...baseFlowState(),
            error: null,
        })

        render(<ConvertPage errorMessage="External error" />)

        expect(screen.getByText('External error')).toBeInTheDocument()
    })

    it('renders excel success message when available', () => {
        mockUseConvertFlow.mockReturnValue({
            ...baseFlowState(),
            excelSuccessMessage: 'Excel exported successfully',
        })

        render(<ConvertPage />)

        expect(screen.getByText('Excel exported successfully')).toBeInTheDocument()
    })
})
