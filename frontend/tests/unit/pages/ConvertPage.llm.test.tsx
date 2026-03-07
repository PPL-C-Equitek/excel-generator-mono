import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ILLMService } from '../../../src/lib/ILLMService'
import type { JsonValue } from '../../../src/utils/schemaValidator'
import ConvertPage from '../../../src/app/convert/ConvertPage'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))

import { uploadFile } from '../../../src/lib/api'
const mockUploadFile = vi.mocked(uploadFile)

vi.mock('../../../src/components/Sidebar', () => ({
    default: () => <div data-testid="sidebar" />,
}))

vi.mock('../../../src/components/UploadZone', () => ({
    default: ({ onFileSelect }: { onFileSelect?: (file: File) => void }) => {
        const file = new File(['content'], 'report.pdf', { type: 'application/pdf' })
        return (
            <div data-testid="upload-zone">
                <button
                    data-testid="upload-btn"
                    onClick={() => onFileSelect?.(file)}
                >
                    Upload File
                </button>
            </div>
        )
    },
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockLLMResult: JsonValue = {
    status: 'ok',
    summary: 'Conversion successful',
    sheets: [
        {
            name: 'Sheet1',
            columns: ['Name', 'Age'],
            rows: [{ Name: 'Alice', Age: 30 }],
        },
    ],
    validations: [],
    errors: [],
}

function makeMockService(result: JsonValue = mockLLMResult): ILLMService {
    return {
        generate: vi.fn().mockResolvedValue({ output_json: result }),
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OUTPUT_FILE_NAME = 'report.xlsx'

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('[RED] ConvertPage — LLM Integration', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUploadFile.mockResolvedValue({
            filename: OUTPUT_FILE_NAME,
            size: 20480,
            format: 'xlsx',
        })
    })

    afterEach(() => {
        vi.resetAllMocks()
    })

    // -----------------------------------------------------------------------
    // 1. Prop: llmService
    // -----------------------------------------------------------------------
    describe('Prop: llmService', () => {
        it('ConvertPage menerima prop llmService bertipe ILLMService', () => {
            const service = makeMockService()
            expect(() => render(<ConvertPage llmService={service} />)).not.toThrow()
        })
    })

    // -----------------------------------------------------------------------
    // 2. Integrasi upload → llmService.generate
    // -----------------------------------------------------------------------
    describe('Upload → LLM flow', () => {
        it('memanggil uploadFile ketika user memilih file', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(mockUploadFile).toHaveBeenCalledTimes(1)
                expect(mockUploadFile).toHaveBeenCalledWith(expect.any(File))
            })
        })

        it('memanggil llmService.generate setelah uploadFile sukses', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(service.generate).toHaveBeenCalledTimes(1)
            })
        })

        it('memanggil llmService.generate dengan data dari response uploadFile', async () => {
            const user = userEvent.setup()
            const uploadResponse = { filename: 'report.pdf', size: 1024, format: 'pdf' }
            mockUploadFile.mockResolvedValue(uploadResponse)
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(service.generate).toHaveBeenCalledWith(
                    expect.objectContaining(uploadResponse)
                )
            })
        })

        it('tidak memanggil llmService.generate jika uploadFile gagal', async () => {
            const user = userEvent.setup()
            mockUploadFile.mockRejectedValue(new Error('Upload failed'))
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(service.generate).not.toHaveBeenCalled()
            })
        })
    })

    // -----------------------------------------------------------------------
    // 3. Loading indicator
    // -----------------------------------------------------------------------
    describe('Loading indicator', () => {
        it('menampilkan loading indicator selama konversi berlangsung', async () => {
            const user = userEvent.setup()
            const service: ILLMService = {
                generate: vi.fn().mockReturnValue(new Promise(() => {})),
            }
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(
                    screen.getByRole('status') ||
                    screen.queryByText(/converting/i) ||
                    screen.queryByText(/processing/i) ||
                    screen.queryByText(/loading/i) ||
                    document.querySelector('[data-testid="loading-indicator"]')
                ).toBeTruthy()
            })
        })

        it('menyembunyikan loading indicator setelah konversi selesai', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(service.generate).toHaveBeenCalled()
            })

            expect(screen.queryByRole('status')).not.toBeInTheDocument()
        })
    })

    // -----------------------------------------------------------------------
    // 4. Hasil konversi sukses
    // -----------------------------------------------------------------------
    describe('Tampilan hasil konversi sukses', () => {
        it('menampilkan nama file output setelah konversi berhasil', async () => {
            const user = userEvent.setup()
            mockUploadFile.mockResolvedValue({ filename: 'report.pdf', size: 1024, format: 'pdf' })
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(screen.getByText(OUTPUT_FILE_NAME)).toBeInTheDocument()
            })
        })

        it('menampilkan format/ekstensi file output setelah konversi berhasil', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(
                    screen.getByText(/xlsx/i) || screen.getByText(/format/i)
                ).toBeInTheDocument()
            })
        })

        it('menampilkan ukuran file output setelah konversi berhasil', async () => {
            const user = userEvent.setup()
            mockUploadFile.mockResolvedValue({ filename: 'report.pdf', size: 20480, format: 'pdf' })
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(
                    screen.getByText(/20\s*KB/i) ||
                    screen.getByText(/20480/i) ||
                    screen.getByText(/ukuran/i) ||
                    screen.getByTestId('file-size')
                ).toBeTruthy()
            })
        })
    })

    // -----------------------------------------------------------------------
    // 5. Tombol Download
    // -----------------------------------------------------------------------
    describe('Tombol Download', () => {
        it('menampilkan tombol Download setelah konversi berhasil', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(
                    screen.getByRole('button', { name: /download/i }) ||
                    screen.getByRole('link', { name: /download/i }) ||
                    screen.getByTestId('download-btn')
                ).toBeTruthy()
            })
        })

        it('tidak menampilkan tombol Download sebelum konversi dilakukan', () => {
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            expect(screen.queryByRole('button', { name: /download/i })).not.toBeInTheDocument()
            expect(screen.queryByTestId('download-btn')).not.toBeInTheDocument()
        })

        it('tombol Download memiliki href atau trigger download yang valid', async () => {
            const user = userEvent.setup()
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                const downloadEl =
                    screen.queryByRole('button', { name: /download/i }) ||
                    screen.queryByRole('link', { name: /download/i }) ||
                    screen.queryByTestId('download-btn')
                expect(downloadEl).toBeInTheDocument()
            })
        })
    })

    // -----------------------------------------------------------------------
    // 6. Error handling
    // -----------------------------------------------------------------------
    describe('Error handling', () => {
        it('menampilkan pesan error jika uploadFile gagal', async () => {
            const user = userEvent.setup()
            mockUploadFile.mockRejectedValue(new Error('Network error: upload failed'))
            const service = makeMockService()
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(screen.getByRole('alert')).toBeInTheDocument()
                expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
            })
        })

        it('menampilkan pesan error jika llmService.generate gagal', async () => {
            const user = userEvent.setup()
            const service: ILLMService = {
                generate: vi.fn().mockRejectedValue(new Error('LLM quota exceeded')),
            }
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(screen.getByRole('alert')).toBeInTheDocument()
                expect(screen.getByText(/quota exceeded/i)).toBeInTheDocument()
            })
        })

        it('pesan error informatif, bukan pesan generik saja', async () => {
            const user = userEvent.setup()
            const errorMessage = 'API key tidak valid'
            const service: ILLMService = {
                generate: vi.fn().mockRejectedValue(new Error(errorMessage)),
            }
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(screen.getByText(new RegExp(errorMessage, 'i'))).toBeInTheDocument()
            })
        })

        it('tidak menampilkan hasil konversi ketika terjadi error', async () => {
            const user = userEvent.setup()
            const service: ILLMService = {
                generate: vi.fn().mockRejectedValue(new Error('Terjadi kesalahan')),
            }
            render(<ConvertPage llmService={service} />)

            await user.click(screen.getByTestId('upload-btn'))

            await waitFor(() => {
                expect(screen.getByRole('alert')).toBeInTheDocument()
            })

            expect(screen.queryByTestId('download-btn')).not.toBeInTheDocument()
            expect(screen.queryByRole('button', { name: /download/i })).not.toBeInTheDocument()
        })
    })
})
