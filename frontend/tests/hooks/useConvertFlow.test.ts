import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useConvertFlow } from '../../src/hooks/useConvertFlow'
import type { ILLMService } from '../../src/lib/ILLMService'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../src/lib/api', () => ({
    uploadFile: vi.fn(),
    fetchAPI: vi.fn(),
}))

vi.mock('../../src/services/llm', () => ({
    generateJson: vi.fn().mockResolvedValue({ output_json: {} }),
    exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_123' }),
    getDownloadUrl: vi.fn().mockReturnValue('/mock/url'),
}))

import { uploadFile } from '../../src/lib/api'
const mockUploadFile = vi.mocked(uploadFile)

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const validUploadResponse = { filename: 'report.pdf', size: 20480, format: 'pdf' }

function makeMockService(overrides?: Partial<ILLMService>): ILLMService {
    return {
        generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
        exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_12345' }),
        getDownloadUrl: vi.fn().mockReturnValue('/api/export/csv/csv_12345/download'),
        ...overrides,
    }
}

const testFile = new File(['content'], 'report.pdf', { type: 'application/pdf' })

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useConvertFlow', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUploadFile.mockResolvedValue(validUploadResponse)
    })

    afterEach(() => {
        vi.unstubAllEnvs()
    })

    // -----------------------------------------------------------------------
    // Initial state
    // -----------------------------------------------------------------------
    describe('initial state', () => {
        it('returns isConverting=false, error=null, outputFile=null on mount', () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            expect(result.current.isConverting).toBe(false)
            expect(result.current.error).toBeNull()
            expect(result.current.outputFile).toBeNull()
        })

        it('exposes handleFileSelect as a function', () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            expect(typeof result.current.handleFileSelect).toBe('function')
        })
    })

    // -----------------------------------------------------------------------
    // Upload flow
    // -----------------------------------------------------------------------
    describe('upload flow', () => {
        it('calls uploadFile with the provided File object', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(mockUploadFile).toHaveBeenCalledWith(testFile, expect.any(Object))
            expect(mockUploadFile).toHaveBeenCalledTimes(1)
        })

        it('calls llmService.generate with the upload response after upload succeeds', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(service.generate).toHaveBeenCalledWith(
                expect.objectContaining(validUploadResponse)
            )
        })

        it('does not call generate if uploadFile throws', async () => {
            mockUploadFile.mockRejectedValue(new Error('Network error'))
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(service.generate).not.toHaveBeenCalled()
        })
    })

    // -----------------------------------------------------------------------
    // Loading state
    // -----------------------------------------------------------------------
    describe('loading state', () => {
        it('sets isConverting=false after successful conversion', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.isConverting).toBe(false)
        })

        it('sets isConverting=false even if generate throws', async () => {
            const service = makeMockService({
                generate: vi.fn().mockRejectedValue(new Error('LLM error')),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.isConverting).toBe(false)
        })
    })

    // -----------------------------------------------------------------------
    // Happy path — outputFile
    // -----------------------------------------------------------------------
    describe('happy path output', () => {
        it('sets outputFile with .xlsx filename derived from upload response', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.outputFile).toEqual({
                filename: 'report.xlsx',
                format: 'xlsx',
                size: 20480,
            })
        })

        it('falls back to file.name when uploadResult has no filename field', async () => {
            mockUploadFile.mockResolvedValue({})
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.outputFile?.filename).toBe('report.xlsx')
            expect(result.current.outputFile?.size).toBe(7)
        })

        it('clears previous error and outputFile when starting a new conversion', async () => {
            // First call fails
            mockUploadFile.mockRejectedValueOnce(new Error('Upload failed'))
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })
            expect(result.current.error).not.toBeNull()

            // Second call succeeds
            mockUploadFile.mockResolvedValue(validUploadResponse)
            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBeNull()
            expect(result.current.outputFile).not.toBeNull()
        })
    })

    // -----------------------------------------------------------------------
    // Schema validation
    // -----------------------------------------------------------------------
    describe('schema validation', () => {
        it('sets error if uploadFile resolves with a non-object value (null)', async () => {
            mockUploadFile.mockResolvedValue(null)
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Respons upload tidak valid')
            expect(service.generate).not.toHaveBeenCalled()
        })

        it('sets error if uploadFile resolves with a string value', async () => {
            mockUploadFile.mockResolvedValue('plain string')
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Respons upload tidak valid')
            expect(service.generate).not.toHaveBeenCalled()
        })
    })

    // -----------------------------------------------------------------------
    // Edge cases and Race Conditions
    // -----------------------------------------------------------------------
    describe('edge cases & race conditions', () => {
        it('ignores stale request if a new request is started before upload completes', async () => {
            let resolveFirst: (v: unknown) => void = () => {}
            let resolveSecond: (v: unknown) => void = () => {}

            mockUploadFile
                .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
                .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            // Start first request
            act(() => { result.current.handleFileSelect(testFile) })
            expect(result.current.isConverting).toBe(true)

            // Start second request
            act(() => { result.current.handleFileSelect(testFile) })

            // Resolve first (stale)
            await act(async () => {
                resolveFirst({ filename: 'stale.pdf', size: 100, format: 'pdf' })
            })

            // Because request is stale, it should not call generate output or throw error
            expect(service.generate).not.toHaveBeenCalledWith(expect.objectContaining({ filename: 'stale.pdf' }))

            // Resolve second (active)
            await act(async () => {
                resolveSecond({ filename: 'active.pdf', size: 200, format: 'pdf' })
            })

            expect(service.generate).toHaveBeenCalledWith(expect.objectContaining({ filename: 'active.pdf' }))
            expect(result.current.outputFile?.filename).toBe('active.xlsx')
        })

        it('ignores stale request if a new request is started before generate completes', async () => {
            let resolveGenerateFirst: (v: unknown) => void = () => {}
            mockUploadFile.mockResolvedValue({ filename: 'test.pdf' })

            const service = makeMockService({
                generate: vi.fn()
                    .mockImplementationOnce(() => new Promise(resolve => { resolveGenerateFirst = resolve }))
                    .mockResolvedValueOnce({ output_json: { ok: true } }) // Second request
            })

            const { result } = renderHook(() => useConvertFlow(service))

            // Start first
            await act(async () => {
                result.current.handleFileSelect(testFile)
            })

            // Start second
            await act(async () => {
                result.current.handleFileSelect(testFile)
            })

            // Resolve first
            await act(async () => {
                resolveGenerateFirst({ output_json: {} })
            })

            // Output should be from second request (second request finished immediately in this mock setup)
            expect(result.current.isConverting).toBe(false)
        })

        it('sets error if uploadFile resolves with an array value', async () => {
            mockUploadFile.mockResolvedValue([1, 2, 3])
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Respons upload tidak valid')
            expect(service.generate).not.toHaveBeenCalled()
        })

        it('parses size correctly if backend returns an empty size or a string size', async () => {
            // Test string size fallback
            mockUploadFile.mockResolvedValue({ filename: 'str.pdf', size: '150' })
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })
            expect(result.current.outputFile?.size).toBe(150)

            // Test completely empty file size to trigger `parsedSize || 0`
            const emptyFile = new File([], 'empty.pdf', { type: 'application/pdf' })
            mockUploadFile.mockResolvedValue({})
            
            await act(async () => {
                await result.current.handleFileSelect(emptyFile)
            })
            // record.size is undefined, file.size is 0, parsedSize is 0, `0 || 0` is 0
            expect(result.current.outputFile?.size).toBe(0)
        })

        it('ignores stale request if a new request is started before upload fails', async () => {
            let rejectFirst: (e: Error) => void = () => {}
            mockUploadFile.mockImplementationOnce(() => new Promise((_, rej) => { rejectFirst = rej }))

            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            // Start first
            act(() => { result.current.handleFileSelect(testFile) })
            
            // Start second immediately (which will succeed)
            mockUploadFile.mockResolvedValueOnce(validUploadResponse)
            await act(async () => { result.current.handleFileSelect(testFile) })

            // Now reject the first one (stale)
            await act(async () => {
                rejectFirst(new Error('Stale upload error'))
            })

            // Error should NOT be set because the rejection was on a stale request
            expect(result.current.error).toBeNull()
        })

        it('ignores stale request if a new request is started before generate fails', async () => {
            let rejectGenerateFirst: (e: Error) => void = () => {}
            mockUploadFile.mockResolvedValue(validUploadResponse)

            const service = makeMockService({
                generate: vi.fn()
                    .mockImplementationOnce(() => new Promise((_, rej) => { rejectGenerateFirst = rej }))
                    .mockResolvedValueOnce({ output_json: { ok: true } }) // Second request
            })

            const { result } = renderHook(() => useConvertFlow(service))

            // Start first
            await act(async () => {
                result.current.handleFileSelect(testFile)
            })

            // Start second (finishes mock immediately)
            await act(async () => {
                result.current.handleFileSelect(testFile)
            })

            // Reject first (stale)
            await act(async () => {
                rejectGenerateFirst(new Error('Stale generate error'))
            })

            // Output should not have the stale error set
            expect(result.current.error).toBeNull()
        })
    })

    // -----------------------------------------------------------------------
    // Error handling
    // -----------------------------------------------------------------------
    describe('error handling', () => {
        it('sets error with message if uploadFile throws an Error instance', async () => {
            mockUploadFile.mockRejectedValue(new Error('Server unreachable'))
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Server unreachable')
        })

        it('sets "Upload failed" fallback if uploadFile throws a non-Error value', async () => {
            mockUploadFile.mockRejectedValue('string error thrown')
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Upload failed')
        })

        it('sets error with message if generate throws an Error instance', async () => {
            const service = makeMockService({
                generate: vi.fn().mockRejectedValue(new Error('LLM quota exceeded')),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('LLM quota exceeded')
            expect(result.current.outputFile).toBeNull()
        })

        it('sets "Conversion failed" fallback if generate throws a non-Error value', async () => {
            const service = makeMockService({
                generate: vi.fn().mockRejectedValue({ code: 500 }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('Conversion failed')
        })

        it('does not set error if uploadFile throws DOMException with name AbortError', async () => {
            const abortError = new DOMException('Aborted', 'AbortError')
            mockUploadFile.mockRejectedValue(abortError)
            
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBeNull() // because aborted requests are ignored
            expect(result.current.isConverting).toBe(true)
        })
    })

    // -----------------------------------------------------------------------
    // Export to CSV Flow
    // -----------------------------------------------------------------------
    describe('export to CSV flow', () => {
        it('initializes csvMetadata as null', () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))
            expect(result.current.csvMetadata).toBeNull()
            
            vi.unstubAllEnvs()
        })

        it('calls exportToCsv after successful LLM generation and sets csvMetadata', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(service.exportToCsv).toHaveBeenCalledWith({ status: 'ok' })
            expect(result.current.csvMetadata).toEqual({ file_id: 'csv_12345' })
            expect(result.current.outputFile?.filename).toBe('report.xlsx')
            
            vi.unstubAllEnvs()
        })

        it('handles exportToCsv error properly', async () => {
            const service = makeMockService({
                exportToCsv: vi.fn().mockRejectedValue(new Error('CSV Export failed'))
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('CSV Export failed')
            expect(result.current.csvMetadata).toBeNull()
            expect(result.current.isConverting).toBe(false)
            
            vi.unstubAllEnvs()
        })

        it('does not call exportToCsv if the service does not implement it', async () => {
            const service: ILLMService = { generate: vi.fn().mockResolvedValue({ output_json: { ok: true } }) }
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.csvMetadata).toBeNull()
            expect(result.current.outputFile?.filename).toBe('report.xlsx')
            
            vi.unstubAllEnvs()
        })

        it('ignores setting csvMetadata if request is aborted during exportToCsv', async () => {
            let resolveExport: (v: unknown) => void = () => {}
            const service = makeMockService({
                exportToCsv: vi.fn()
                   .mockImplementationOnce(() => new Promise((resolve) => { resolveExport = resolve }))
                   .mockResolvedValueOnce({ file_id: 'csv_999' }) // second request
            })
            
            const { result } = renderHook(() => useConvertFlow(service))

            // Start first
            act(() => { result.current.handleFileSelect(testFile) })
            
            // Wait for it to specifically reach exportToCsv
            await waitFor(() => expect(service.exportToCsv).toHaveBeenCalledTimes(1))
            
            // Start second request (which will abort the first)
            await act(async () => { await result.current.handleFileSelect(testFile) })
            
            // Now resolve the first request which is stale and aborted
            await act(async () => { resolveExport({ file_id: 'csv_stale' }) })

            // The active request will set it to csv_999, so it should not be 'csv_stale'
            expect(result.current.csvMetadata?.file_id).toBe('csv_999')
            
            vi.unstubAllEnvs()
        })
    })

    // -----------------------------------------------------------------------
    // Security & Edge Cases (CSV Export)
    // -----------------------------------------------------------------------
    describe('security & edge cases for CSV export', () => {
        it('prevents CSV Injection by prepending single quotes to cells starting with =, +, -, @', async () => {
            const rawOutput = {
                sheet1: [
                    { col1: '=1+1', col2: '-cmd', col3: '+alert(1)', col4: '@sum' }
                ]
            }
            const expectedPayload = {
                sheet1: [
                    { col1: "'=1+1", col2: "'-cmd", col3: "'+alert(1)", col4: "'@sum" }
                ]
            }

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: rawOutput })
            })
            
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            // generate() receives exactly what was originally intended by standard flows
            // but exportToCsv expects the SANITIZED version
            expect(service.exportToCsv).toHaveBeenCalledWith(expectedPayload)
            
            vi.unstubAllEnvs()
        })

        it('preserves special characters like commas, quotes, and newlines correctly without breaking JSON', async () => {
            const rawOutput = {
                sheet1: [
                    { col1: 'hello, world', col2: 'say "hi"', col3: 'line1\nline2' }
                ]
            }

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: rawOutput })
            })
            
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            // These characters do not require prepending single quotes, they just pass through cleanly
            expect(service.exportToCsv).toHaveBeenCalledWith(rawOutput)
            
            vi.unstubAllEnvs()
        })

        it('blocks empty API calls and sets warning if LLM returns an empty string or empty object/array', async () => {
            const emptyOutputs = [{}, [], "", null]
            
            for (const emptyVal of emptyOutputs) {
                const service = makeMockService({
                    generate: vi.fn().mockResolvedValue({ output_json: emptyVal })
                })
                
                const { result } = renderHook(() => useConvertFlow(service))

                await act(async () => {
                    await result.current.handleFileSelect(testFile)
                })

                expect(service.exportToCsv).not.toHaveBeenCalled()
                expect(result.current.csvMetadata).toBeNull()
                // Assuming we want to set a specific error message for empty payload edge cases
                expect(result.current.error).toBe('Data tidak valid atau kosong, tidak dapat mengekspor CSV')
            }
            
            vi.unstubAllEnvs()
        })

        it('synchronizes and exports all multi-sheet data without omitting any payload sheets', async () => {
            const rawOutput = {
                sheet1: [{ id: 1, val: 'a' }],
                sheet2: [{ id: 2, val: 'b' }],
                sheet3: [{ id: 3, val: 'c' }]
            }

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: rawOutput })
            })
            
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            // Expect that exportToCsv is called with the exact full structure spanning all sheets
            expect(service.exportToCsv).toHaveBeenCalledWith(rawOutput)
            
            vi.unstubAllEnvs()
        })
    })
})
