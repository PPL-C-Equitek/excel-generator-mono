import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ILLMService } from '../../../src/lib/ILLMService'

vi.mock('../../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))

import { uploadFile } from '../../../src/lib/api'

vi.mock('../../../src/components/UploadZone', () => ({
    default: ({
        onFileSelect,
    }: {
        onFileSelect?: (file: File) => void
    }) => (
        <button
            type="button"
            onClick={() => {
                onFileSelect?.(new File(['content'], 'schema-test.pdf', { type: 'application/pdf' }))
            }}
        >
            Upload File
        </button>
    ),
}))

vi.mock('../../../src/components/Sidebar', () => ({
    default: () => <div>Sidebar</div>,
}))

vi.mock('../../../src/components/SchemaSelector', () => ({
    default: ({
        onSchemaChange,
    }: {
        onSchemaChange?: (schema: { id: string } | null) => void
    }) => (
        <button
            type="button"
            onClick={() => {
                onSchemaChange?.({ id: '11111111-1111-1111-1111-111111111111' })
            }}
        >
            Select Schema
        </button>
    ),
}))

import ConvertPage from '../../../src/app/convert/ConvertPage'

const mockUploadFile = vi.mocked(uploadFile)

describe('ConvertPage schema integration', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUploadFile.mockResolvedValue({
            filename: 'schema-test.pdf',
            size: 10240,
            format: 'pdf',
        })
    })

    it('passes the selected schema id into the convert flow', async () => {
        const user = userEvent.setup()
        const llmService: ILLMService = {
            generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
            exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_12345' }),
            getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_12345/download'),
        }

        render(<ConvertPage llmService={llmService} />)

        await user.click(screen.getByText('Select Schema'))
        await user.click(screen.getByText('Upload File'))

        await waitFor(() => {
            expect(llmService.generate).toHaveBeenCalledWith(
                expect.objectContaining({ filename: 'schema-test.pdf' }),
                '11111111-1111-1111-1111-111111111111'
            )
        })
    })
})
