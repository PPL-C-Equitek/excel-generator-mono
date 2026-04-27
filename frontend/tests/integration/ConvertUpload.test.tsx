import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import ConvertPage from '../../src/app/convert/ConvertPage'
import { uploadFile } from '../../src/lib/api'

// Mock the API calls but NOT UploadZone or useConvertFlow
vi.mock('../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))
vi.mock('../../src/services/llm', () => ({
    generateJson: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
    exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_integration' }),
    downloadCsvFile: vi.fn().mockResolvedValue(undefined),
    downloadSessionOutputCsvFile: vi.fn().mockResolvedValue(undefined),
    exportToExcel: vi.fn().mockResolvedValue({
        file_id: 'xlsx_integration',
        file_name: 'export_integration.xlsx',
        artifact_type: 'xlsx',
    }),
    downloadExcelFile: vi.fn().mockResolvedValue(undefined),
    downloadSessionOutputExcelFile: vi.fn().mockResolvedValue(undefined),
    getDownloadUrl: vi.fn().mockReturnValue('/mock/url'),
}))
vi.mock('../../src/components/Sidebar', () => ({
    default: () => <div data-testid="sidebar">Sidebar</div>,
}))

const mockUploadFile = vi.mocked(uploadFile)

describe('Integration: ConvertPage & UploadZone', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUploadFile.mockResolvedValue({ filename: 'test.xlsx', size: 1024, format: 'xlsx' })
    })

    afterEach(() => {
        vi.unstubAllEnvs()
    })

    it('ensures confirming a file selection results in exactly one upload API call', async () => {
        const user = userEvent.setup()
        render(<ConvertPage />)

        const fileInput = screen.getByTestId('file-input')
        const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        await user.upload(fileInput, file)
        await user.click(screen.getByTestId('convert-btn'))
        await waitFor(() => {
            expect(mockUploadFile).toHaveBeenCalledTimes(1)
        })
    })
})
