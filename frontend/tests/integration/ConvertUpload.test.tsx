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

    it('ensures a single file selection action results in exactly one upload API call', async () => {
        const user = userEvent.setup()
        render(<ConvertPage />)

        const fileInput = screen.getByTestId('file-input')
        const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })

        // Simulate ONE user action (selecting a file)
        await user.upload(fileInput, file)

        await waitFor(() => {
            // Assert exactly one upload call
            expect(mockUploadFile).toHaveBeenCalledTimes(1)
        })
    })
})
