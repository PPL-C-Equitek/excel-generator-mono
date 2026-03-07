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
            expect(result.current.outputFile?.size).toBe(0)
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
