import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import ConvertPage from '../../src/app/convert/ConvertPage'
import { uploadFile } from '../../src/lib/api'
import { generateJson } from '../../src/services/llm'

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
const mockGenerateJson = vi.mocked(generateJson)

describe('Integration: ConvertPage & UploadZone', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUploadFile.mockResolvedValue({ filename: 'test.xlsx', size: 1024, format: 'xlsx' })
        mockGenerateJson.mockResolvedValue({ output_json: { status: 'ok' } })
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

    it('uses the latest generated output as context when sending a follow-up refinement', async () => {
        const user = userEvent.setup()
        const firstOutput = { rows: [{ status: 'all' }] }
        const secondOutput = { rows: [{ status: 'paid' }] }
        mockGenerateJson
            .mockResolvedValueOnce({ output_json: firstOutput })
            .mockResolvedValueOnce({ output_json: secondOutput })

        render(<ConvertPage />)

        const fileInput = screen.getByTestId('file-input')
        const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        await user.upload(fileInput, file)
        await user.click(screen.getByTestId('convert-btn'))

        await waitFor(() => {
            expect(screen.getByText('Your file is ready.')).toBeInTheDocument()
        })

        await user.type(screen.getByLabelText('Follow-up message'), 'Only keep paid invoices')
        await user.click(screen.getByRole('button', { name: /send/i }))

        await waitFor(() => {
            expect(mockGenerateJson).toHaveBeenCalledTimes(2)
        })
        expect(mockUploadFile).toHaveBeenCalledTimes(1)
        expect(mockGenerateJson).toHaveBeenNthCalledWith(
            2,
            expect.objectContaining({
                previous_output: firstOutput,
                user_prompt: 'Only keep paid invoices',
            }),
            undefined,
            expect.any(AbortSignal)
        )
    })

    it('reveals backend reasoning steps before showing the final thinking log', async () => {
        const user = userEvent.setup()
        mockGenerateJson.mockResolvedValue({
            output_json: { status: 'ok' },
            reasoning: {
                final_answer: 'Done',
                reasoning_steps: ['Reviewed uploaded content', 'Mapped data into the target structure'],
                thinking_log: 'Final thinking log from backend.',
            },
        })

        render(<ConvertPage />)

        const fileInput = screen.getByTestId('file-input')
        const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        await user.upload(fileInput, file)
        await user.click(screen.getByTestId('convert-btn'))

        await waitFor(() => {
            expect(screen.getByText('Reviewed uploaded content')).toBeInTheDocument()
        })
        expect(screen.queryByText('Final thinking log from backend.')).not.toBeInTheDocument()

        await waitFor(() => {
            expect(screen.getByText('Mapped data into the target structure')).toBeInTheDocument()
        })
        expect(screen.queryByText('Final thinking log from backend.')).not.toBeInTheDocument()

        await waitFor(() => {
            expect(screen.getByText('Final thinking log from backend.')).toBeInTheDocument()
        }, { timeout: 2000 })
    })
})
