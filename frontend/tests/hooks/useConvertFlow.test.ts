import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
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

            expect(mockUploadFile).toHaveBeenCalledWith(testFile)
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
            let resolveFirst: (v: any) => void = () => {}
            let resolveSecond: (v: any) => void = () => {}

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
            let resolveGenerateFirst: (v: any) => void = () => {}
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

        it('computes correct outputFile when uploadResult is an array instead of object', async () => {
            mockUploadFile.mockResolvedValue([1, 2, 3])
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            // Because it's an array, record is null, falls back to file.name and file.size (or 0)
            expect(result.current.outputFile?.filename).toBe('report.xlsx')
            expect(result.current.outputFile?.size).toBe(7)
        })

        it('parses size correctly if backend returns an empty size or a string size', async () => {
            // Test string size fallback
            mockUploadFile.mockResolvedValue({ filename: 'str.pdf', size: '150' })
            const service = makeMockService()
            const { result, rerender } = renderHook(() => useConvertFlow(service))

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
    })
})
