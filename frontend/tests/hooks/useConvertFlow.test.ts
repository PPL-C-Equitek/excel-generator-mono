import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useConvertFlow } from '../../src/hooks/useConvertFlow'
import type { ILLMService } from '../../src/lib/ILLMService'
import { FILE_TOO_LARGE_MESSAGE, MAX_UPLOAD_SIZE_BYTES } from '../../src/constants/upload'

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
    downloadCsvFile: vi.fn().mockResolvedValue(undefined),
    exportToExcel: vi.fn().mockResolvedValue({
        file_id: 'xlsx_123',
        file_name: 'export_123.xlsx',
        artifact_type: 'xlsx',
    }),
    downloadExcelFile: vi.fn().mockResolvedValue(undefined),
    getDownloadUrl: vi.fn().mockReturnValue('/mock/url'),
}))

import { uploadFile } from '../../src/lib/api'
const mockUploadFile = vi.mocked(uploadFile)

type UseConvertFlowExcelState = ReturnType<typeof useConvertFlow> & {
    canDownloadExcel: boolean
    isExcelDownloading: boolean
    excelError: string | null
    excelSuccessMessage: string | null
    handleExcelDownload: () => Promise<void>
}

type UseConvertFlowDownloadState = UseConvertFlowExcelState & {
    canDownloadCsv: boolean
    handleCsvDownload: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const validUploadResponse = { filename: 'report.pdf', size: 20480, format: 'pdf' }
const validExcelExportResponse = {
    file_id: 'xlsx_12345',
    file_name: 'export_12345.xlsx',
    artifact_type: 'xlsx' as const,
}

const expectedExcelExportPayload = {
    document_info: {
        source_type: 'PDF',
        filename: 'report.pdf',
    },
    summary: {
        total_tables: 1,
        total_rows: 1,
        total_columns: 1,
    },
    content_data: [
        {
            table_name: 'Sheet1',
            headers: ['status'],
            rows: [{ status: 'ok' }],
        },
    ],
}

const expectedCsvExportPayload = {
    document_info: {
        source_type: 'PDF',
        filename: 'report.pdf',
    },
    summary: {
        total_tables: 1,
        total_rows: 1,
        total_columns: 1,
    },
    content_data: [
        {
            table_name: 'Sheet1',
            headers: ['status'],
            rows: [{ status: 'ok' }],
        },
    ],
}

function deferred<T>() {
    let resolve!: (value: T | PromiseLike<T>) => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<T>((res, rej) => {
        resolve = res
        reject = rej
    })

    return { promise, resolve, reject }
}

function getExcelState(result: { current: ReturnType<typeof useConvertFlow> }): UseConvertFlowExcelState {
    return result.current as UseConvertFlowExcelState
}

function getDownloadState(result: { current: ReturnType<typeof useConvertFlow> }): UseConvertFlowDownloadState {
    return result.current as UseConvertFlowDownloadState
}

function makeMockService(overrides?: Partial<ILLMService>): ILLMService {
    return {
        generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
        exportToCsv: vi.fn().mockResolvedValue({ file_id: 'csv_12345' }),
        downloadCsvFile: vi.fn().mockResolvedValue(undefined),
        exportToExcel: vi.fn().mockResolvedValue(validExcelExportResponse),
        downloadExcelFile: vi.fn().mockResolvedValue(undefined),
        getDownloadUrl: vi.fn().mockReturnValue('/export/csv/csv_12345/download'),
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
                expect.objectContaining(validUploadResponse),
                undefined,
                expect.any(AbortSignal)
            )
        })

        it('uses validated_json for export when server returns refinement result', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: { status: 'raw' },
                    validated_json: {
                        document_info: {
                            source_type: 'PDF',
                            filename: 'report.pdf',
                        },
                        summary: {
                            total_tables: 1,
                            total_rows: 1,
                            total_columns: 1,
                        },
                        content_data: [
                            {
                                table_name: 'Sheet1',
                                headers: ['status'],
                                rows: [{ status: 'validated' }],
                            },
                        ],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledWith(
                {
                    document_info: {
                        source_type: 'PDF',
                        filename: 'report.pdf',
                    },
                    summary: {
                        total_tables: 1,
                        total_rows: 1,
                        total_columns: 1,
                    },
                    content_data: [
                        {
                            table_name: 'Sheet1',
                            headers: ['status'],
                            rows: [{ status: 'validated' }],
                        },
                    ],
                },
                expect.any(AbortSignal)
            )
        })

        it('passes the selected custom schema id into llmService.generate when provided', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(
                    testFile,
                    '11111111-1111-1111-1111-111111111111'
                )
            })

            expect(service.generate).toHaveBeenCalledWith(
                expect.objectContaining(validUploadResponse),
                '11111111-1111-1111-1111-111111111111',
                expect.any(AbortSignal)
            )
        })

        it('passes AbortSignal into llmService.generate after upload succeeds', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(service.generate).toHaveBeenCalledWith(
                expect.objectContaining(validUploadResponse),
                undefined,
                expect.any(AbortSignal)
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

        it('rejects files larger than 10MB on frontend before uploading', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))
            const oversizedFile = new File(['x'], 'big.pdf', { type: 'application/pdf' })
            Object.defineProperty(oversizedFile, 'size', { value: MAX_UPLOAD_SIZE_BYTES + 1 })

            await act(async () => {
                await result.current.handleFileSelect(oversizedFile)
            })

            expect(mockUploadFile).not.toHaveBeenCalled()
            expect(service.generate).not.toHaveBeenCalled()
            expect(result.current.error).toBe(FILE_TOO_LARGE_MESSAGE)
            expect(result.current.isConverting).toBe(false)
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
        it('sets outputFile filename and format from upload response', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.outputFile).toEqual({
                filename: 'report.pdf',
                format: 'pdf',
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

            expect(result.current.outputFile?.filename).toBe('report.pdf')
            expect(result.current.outputFile?.format).toBe('pdf')
            expect(result.current.outputFile?.size).toBe(7)
        })

        it('uses document_info.filename when backend returns parsed upload payload', async () => {
            mockUploadFile.mockResolvedValue({
                document_info: { filename: 'from-parser.pdf', source_type: 'PDF' },
                summary: { total_tables: 1, total_rows: 1, total_columns: 1 },
                content_data: [{ table_name: 'PDF_Content', headers: ['text'], rows: [{ text: 'hello' }] }],
            })
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.outputFile?.filename).toBe('from-parser.pdf')
            expect(result.current.outputFile?.format).toBe('pdf')
        })

        it('infers format from fallback file mime type when filename has no extension', async () => {
            mockUploadFile.mockResolvedValue({ filename: 'from-parser' })
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.outputFile?.filename).toBe('from-parser')
            expect(result.current.outputFile?.format).toBe('pdf')
        })

        it('falls back to "bin" when filename has no extension and mime type is empty', async () => {
            mockUploadFile.mockResolvedValue({ filename: 'noext' })
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))
            const unknownFile = new File(['content'], 'noext', { type: '' })

            await act(async () => {
                await result.current.handleFileSelect(unknownFile)
            })

            expect(result.current.outputFile?.filename).toBe('noext')
            expect(result.current.outputFile?.format).toBe('bin')
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

            expect(result.current.error).toBe('The server returned an invalid upload response.')
            expect(service.generate).not.toHaveBeenCalled()
        })

        it('sets error if uploadFile resolves with a string value', async () => {
            mockUploadFile.mockResolvedValue('plain string')
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(result.current.error).toBe('The server returned an invalid upload response.')
            expect(service.generate).not.toHaveBeenCalled()
        })
    })

    // -----------------------------------------------------------------------
    // Edge cases and Race Conditions
    // -----------------------------------------------------------------------
    describe('edge cases & race conditions', () => {
        it('ignores stale request if a new request is started before upload completes', async () => {
            let resolveFirst: (v: unknown) => void = () => { }
            let resolveSecond: (v: unknown) => void = () => { }

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

            expect(service.generate).toHaveBeenCalledWith(
                expect.objectContaining({ filename: 'active.pdf' }),
                undefined,
                expect.any(AbortSignal)
            )
            expect(result.current.outputFile?.filename).toBe('active.pdf')
        })

        it('ignores stale request if a new request is started before generate completes', async () => {
            let resolveGenerateFirst: (v: unknown) => void = () => { }
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

            expect(result.current.error).toBe('The server returned an invalid upload response.')
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
            let rejectFirst: (e: Error) => void = () => { }
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
            let rejectGenerateFirst: (e: Error) => void = () => { }
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

        it('aborts the previous generate signal when a new conversion starts', async () => {
            let firstSignal: AbortSignal | undefined
            const firstGenerate = deferred<{ output_json: { ok: boolean } }>()
            const service = makeMockService({
                generate: vi.fn()
                    .mockImplementationOnce((_, __, signal?: AbortSignal) => {
                        firstSignal = signal
                        return firstGenerate.promise
                    })
                    .mockResolvedValueOnce({ output_json: { ok: true } }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                void result.current.handleFileSelect(testFile)
                await Promise.resolve()
            })

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(firstSignal?.aborted).toBe(true)
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

        it('exports and downloads csv on explicit request and sets csvMetadata', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledWith(
                expectedCsvExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadCsvFile).toHaveBeenCalledWith('csv_12345', 'report.csv')
            expect(result.current.csvMetadata).toEqual({ file_id: 'csv_12345' })
            expect(result.current.outputFile?.filename).toBe('report.pdf')

            vi.unstubAllEnvs()
        })

        it('handles exportToCsv error properly when download is requested', async () => {
            const service = makeMockService({
                exportToCsv: vi.fn().mockRejectedValue(new Error('CSV Export failed'))
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
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

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(result.current.csvMetadata).toBeNull()
            expect(result.current.outputFile?.filename).toBe('report.pdf')

            vi.unstubAllEnvs()
        })

        it('stores csv error when the download step fails', async () => {
            const service = makeMockService({
                downloadCsvFile: vi.fn().mockRejectedValue(new Error('Failed to export'))
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledWith(
                expectedCsvExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadCsvFile).toHaveBeenCalledWith('csv_12345', 'report.csv')
            expect(result.current.error).toBe('Failed to export')
            expect(result.current.csvMetadata).toEqual({ file_id: 'csv_12345' })
        })

        it('uses the fallback csv error message for non-Error failures', async () => {
            const service = makeMockService({
                exportToCsv: vi.fn().mockRejectedValue('fatal')
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(result.current.error).toBe('CSV Export failed')
            expect(result.current.csvMetadata).toBeNull()
        })

        it('does not export csv when output is not ready', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).not.toHaveBeenCalled()
            expect(result.current.csvMetadata).toBeNull()
        })

        it('ignores setting csvMetadata if request is aborted during manual exportToCsv', async () => {
            let resolveExport: (v: unknown) => void = () => { }
            const service = makeMockService({
                exportToCsv: vi.fn()
                    .mockImplementationOnce(() => new Promise((resolve) => { resolveExport = resolve }))
                    .mockResolvedValueOnce({ file_id: 'csv_999' }) // second request
            })

            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => { void getDownloadState(result).handleCsvDownload() })
            await waitFor(() => expect(service.exportToCsv).toHaveBeenCalledTimes(1))

            // Start second conversion, which clears stale CSV metadata/results
            await act(async () => { await result.current.handleFileSelect(testFile) })

            // Now resolve the first request which is stale and aborted
            await act(async () => { resolveExport({ file_id: 'csv_stale' }) })

            expect(result.current.csvMetadata).toBeNull()

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
                document_info: {
                    source_type: 'PDF',
                    filename: 'report.pdf',
                },
                summary: {
                    total_tables: 1,
                    total_rows: 1,
                    total_columns: 4,
                },
                content_data: [
                    {
                        table_name: 'sheet1',
                        headers: ['col1', 'col2', 'col3', 'col4'],
                        rows: [{ col1: "'=1+1", col2: "'-cmd", col3: "'+alert(1)", col4: "'@sum" }],
                    },
                ],
            }

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: rawOutput })
            })

            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            // generate() receives exactly what was originally intended by standard flows
            // but exportToCsv expects the SANITIZED version
            expect(service.exportToCsv).toHaveBeenCalledWith(
                expectedPayload,
                expect.any(AbortSignal)
            )

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

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            // These characters do not require prepending single quotes, they just pass through cleanly
            expect(service.exportToCsv).toHaveBeenCalledWith(
                {
                    document_info: {
                        source_type: 'PDF',
                        filename: 'report.pdf',
                    },
                    summary: {
                        total_tables: 1,
                        total_rows: 1,
                        total_columns: 3,
                    },
                    content_data: [
                        {
                            table_name: 'sheet1',
                            headers: ['col1', 'col2', 'col3'],
                            rows: [{ col1: 'hello, world', col2: 'say "hi"', col3: 'line1\nline2' }],
                        },
                    ],
                },
                expect.any(AbortSignal)
            )

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

                await act(async () => {
                    await getDownloadState(result).handleCsvDownload()
                })

                expect(service.exportToCsv).not.toHaveBeenCalled()
                expect(result.current.csvMetadata).toBeNull()
                expect(result.current.error).toBe("The converted data is empty or invalid, so it can't be exported.")
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

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            // Expect that exportToCsv is called with the exact full structure spanning all sheets
            expect(service.exportToCsv).toHaveBeenCalledWith(
                {
                    document_info: {
                        source_type: 'PDF',
                        filename: 'report.pdf',
                    },
                    summary: {
                        total_tables: 3,
                        total_rows: 3,
                        total_columns: 2,
                    },
                    content_data: [
                        {
                            table_name: 'sheet1',
                            headers: ['id', 'val'],
                            rows: [{ id: 1, val: 'a' }],
                        },
                        {
                            table_name: 'sheet2',
                            headers: ['id', 'val'],
                            rows: [{ id: 2, val: 'b' }],
                        },
                        {
                            table_name: 'sheet3',
                            headers: ['id', 'val'],
                            rows: [{ id: 3, val: 'c' }],
                        },
                    ],
                },
                expect.any(AbortSignal)
            )

            vi.unstubAllEnvs()
        })

        it('throws an error if the exported CSV file_id does not start with csv_', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: { test: 'ok' } }),
                exportToCsv: vi.fn().mockResolvedValue({ file_id: 'invalid_id_123' })
            })

            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(result.current.csvMetadata).toBeNull()
            expect(result.current.error).toBe('The export result is invalid. Please try again.')

            vi.unstubAllEnvs()
        })

        it('does not auto-export CSV immediately after conversion succeeds', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(service.exportToCsv).not.toHaveBeenCalled()
            expect(result.current.csvMetadata).toBeNull()
            expect(getDownloadState(result).canDownloadCsv).toBe(true)
        })

        it('exports CSV only when the user explicitly requests download', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledTimes(1)
            expect(service.exportToCsv).toHaveBeenCalledWith(
                expectedCsvExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadCsvFile).toHaveBeenCalledTimes(1)
            expect(service.downloadCsvFile).toHaveBeenCalledWith('csv_12345', 'report.csv')
            expect(result.current.csvMetadata).toEqual({ file_id: 'csv_12345' })
        })

        it('passes AbortSignal into exportToCsv when the user downloads CSV', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledWith(
                expectedCsvExportPayload,
                expect.any(AbortSignal)
            )
        })

        it('reuses cached csv metadata and downloads again without exporting again', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledTimes(1)
            expect(service.downloadCsvFile).toHaveBeenCalledTimes(2)
            expect(result.current.csvMetadata).toEqual({ file_id: 'csv_12345' })
        })

        it('ignores stale csv export failures after a newer conversion starts', async () => {
            const firstExport = deferred<{ file_id: string }>()
            const service = makeMockService({
                exportToCsv: vi.fn()
                    .mockImplementationOnce(() => firstExport.promise)
                    .mockResolvedValueOnce({ file_id: 'csv_99999' })
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getDownloadState(result).handleCsvDownload()
            })

            await waitFor(() => expect(service.exportToCsv).toHaveBeenCalledTimes(1))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                firstExport.reject(new Error('stale csv export failure'))
                await Promise.resolve()
            })

            expect(result.current.error).toBeNull()
            expect(result.current.csvMetadata).toBeNull()
        })

        it('normalizes duplicate and blank headers in direct headers/rows output', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: {
                        headers: ['Name', 'name', '   '],
                        rows: [[1, 2, 3]],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['Name', 'name_2', 'column_3'])
            expect(payload.content_data[0].rows[0]).toEqual({ Name: 1, name_2: 2, column_3: 3 })
        })

        it('falls back to value header when direct headers array is empty', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: {
                        headers: [],
                        rows: [[123]],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['value'])
            expect(payload.content_data[0].rows[0]).toEqual({ value: 123 })
        })

        it('maps unknown row values with null padding when headers have multiple columns', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: {
                        headers: ['first', 'second'],
                        rows: ['raw-text-row'],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].rows[0]).toEqual({ first: 'raw-text-row', second: null })
        })

        it('builds tabular payload from array-of-arrays output', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: [[1, 2], [3]] }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['column_1', 'column_2'])
            expect(payload.content_data[0].rows).toEqual([
                { column_1: 1, column_2: 2 },
                { column_1: 3, column_2: null },
            ])
        })

        it('builds tabular payload from scalar array output', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: ['alpha', 2, true] }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['value'])
            expect(payload.content_data[0].rows).toEqual([
                { value: 'alpha' },
                { value: 2 },
                { value: true },
            ])
        })

        it('builds tabular payload from scalar output', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: 42 }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['value'])
            expect(payload.content_data[0].rows).toEqual([{ value: 42 }])
        })

        it('serializes object cells and safely falls back for circular values', async () => {
            const circular: { self?: unknown } = {}
            circular.self = circular

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: {
                        headers: ['plain_obj', 'circular_obj'],
                        rows: [[{ nested: 'ok' }, circular]],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].rows[0]).toEqual({
                plain_obj: '{"nested":"ok"}',
                circular_obj: '[Unserializable Value]',
            })
        })

        it('uses upload document_info source_type and filename priorities in canonical payload', async () => {
            mockUploadFile.mockResolvedValue({
                document_info: {
                    source_type: ' excel ',
                    filename: 'nested-name.pdf',
                },
            })

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
            })

            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                document_info: { source_type: string; filename: string }
            }

            expect(payload.document_info).toEqual({
                source_type: 'Excel',
                filename: 'nested-name.pdf',
            })
        })

        it('resolves PDF source_type from upload metadata and falls back to output filename', async () => {
            mockUploadFile.mockResolvedValue({
                document_info: {
                    source_type: ' PDF ',
                },
            })

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
            })

            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                document_info: { source_type: string; filename: string }
            }

            expect(payload.document_info).toEqual({
                source_type: 'PDF',
                filename: 'report.pdf',
            })
        })

        it('passes through canonical export payload without rebuilding it', async () => {
            const canonicalOutput = {
                document_info: {
                    source_type: 'PDF',
                    filename: 'canonical.pdf',
                },
                summary: {
                    total_tables: 1,
                    total_rows: 1,
                    total_columns: 1,
                },
                content_data: [
                    {
                        table_name: 'SheetCanonical',
                        headers: ['status'],
                        rows: [{ status: 'ready' }],
                    },
                ],
            }

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: canonicalOutput }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            expect(service.exportToCsv).toHaveBeenCalledWith(
                canonicalOutput,
                expect.any(AbortSignal)
            )
        })

        it('fills missing object-row fields with null when inferring union headers', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: [{ a: 1 }, { b: 2 }],
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ headers: string[]; rows: Array<Record<string, unknown>> }>
            }

            expect(payload.content_data[0].headers).toEqual(['a', 'b'])
            expect(payload.content_data[0].rows).toEqual([
                { a: 1, b: null },
                { a: null, b: 2 },
            ])
        })

        it('uses generated fallback sheet name when a sheet key is blank', async () => {
            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({
                    output_json: {
                        '': [{ value: 'first' }],
                        sheet2: [{ value: 'second' }],
                    },
                }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                content_data: Array<{ table_name: string }>
            }

            expect(payload.content_data[0].table_name).toBe('Sheet1')
            expect(payload.content_data[1].table_name).toBe('sheet2')
        })

        it('falls back to output format when source_type is unrecognized', async () => {
            mockUploadFile.mockResolvedValue({
                filename: 'report.xlsx',
                document_info: {
                    source_type: 'word',
                },
            })

            const service = makeMockService({
                generate: vi.fn().mockResolvedValue({ output_json: { status: 'ok' } }),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getDownloadState(result).handleCsvDownload()
            })

            const payload = (service.exportToCsv as ReturnType<typeof vi.fn>).mock.calls[0][0] as {
                document_info: { source_type: string; filename: string }
            }

            expect(payload.document_info).toEqual({
                source_type: 'Excel',
                filename: 'report.xlsx',
            })
        })

    })

    // -----------------------------------------------------------------------
    // Export to Excel Flow
    // -----------------------------------------------------------------------
    describe('export to Excel flow', () => {
        it('initializes excel state as idle and unavailable', () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))
            const current = getExcelState(result)

            expect(current.canDownloadExcel).toBe(false)
            expect(current.isExcelDownloading).toBe(false)
            expect(current.excelError).toBeNull()
            expect(current.excelSuccessMessage).toBeNull()
            expect(typeof current.handleExcelDownload).toBe('function')
        })

        it('does not start excel export when converted output is not ready', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))
            const current = getExcelState(result)

            await act(async () => {
                await current.handleExcelDownload()
            })

            expect(service.exportToExcel).not.toHaveBeenCalled()
            expect(service.downloadExcelFile).not.toHaveBeenCalled()
            expect(current.canDownloadExcel).toBe(false)
            expect(current.isExcelDownloading).toBe(false)
            expect(current.excelError).toBeNull()
        })

        it('starts excel export and downloads the file when converted output is ready', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledWith(
                expectedExcelExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadExcelFile).toHaveBeenCalledWith(
                'xlsx_12345',
                'report.xlsx'
            )
            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBe('Successfully downloaded')
        })

        it('passes AbortSignal into exportToExcel when the user downloads excel', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledWith(
                expectedExcelExportPayload,
                expect.any(AbortSignal)
            )
        })

        it('sets isExcelDownloading while the excel request is in flight', async () => {
            const excelExportDeferred = deferred<typeof validExcelExportResponse>()
            const service = makeMockService({
                exportToExcel: vi.fn().mockReturnValue(excelExportDeferred.promise),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getExcelState(result).handleExcelDownload()
            })

            expect(getExcelState(result).isExcelDownloading).toBe(true)

            await act(async () => {
                excelExportDeferred.resolve(validExcelExportResponse)
                await excelExportDeferred.promise
            })

            expect(getExcelState(result).isExcelDownloading).toBe(false)
        })

        it('ignores repeated excel clicks while a request is already active', async () => {
            const excelExportDeferred = deferred<typeof validExcelExportResponse>()
            const service = makeMockService({
                exportToExcel: vi.fn().mockReturnValue(excelExportDeferred.promise),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getExcelState(result).handleExcelDownload()
            })
            act(() => {
                void getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(1)
            expect(service.downloadExcelFile).not.toHaveBeenCalled()

            await act(async () => {
                excelExportDeferred.resolve(validExcelExportResponse)
                await excelExportDeferred.promise
            })
        })

        it('stores excel error when the export step fails', async () => {
            const service = makeMockService({
                exportToExcel: vi.fn().mockRejectedValue(new Error('Excel export failed')),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledWith(
                expectedExcelExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadExcelFile).not.toHaveBeenCalled()
            expect(getExcelState(result).isExcelDownloading).toBe(false)
            expect(getExcelState(result).excelError).toBe('Excel export failed')
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
        })

        it('stores excel error when the download step fails', async () => {
            const service = makeMockService({
                downloadExcelFile: vi.fn().mockRejectedValue(new Error('Failed to export')),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledWith(
                expectedExcelExportPayload,
                expect.any(AbortSignal)
            )
            expect(service.downloadExcelFile).toHaveBeenCalledWith(
                'xlsx_12345',
                'report.xlsx'
            )
            expect(getExcelState(result).isExcelDownloading).toBe(false)
            expect(getExcelState(result).excelError).toBe('Failed to export')
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
        })

        it('falls back to the default excel error message when the failure is not an Error instance', async () => {
            const service = makeMockService({
                downloadExcelFile: vi.fn().mockRejectedValue('fatal'),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(getExcelState(result).isExcelDownloading).toBe(false)
            expect(getExcelState(result).excelError).toBe('Failed to export')
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
        })

        it('clears previous excel error after a successful second attempt', async () => {
            const service = makeMockService({
                exportToExcel: vi.fn()
                    .mockRejectedValueOnce(new Error('Excel export failed'))
                    .mockResolvedValueOnce(validExcelExportResponse),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(getExcelState(result).excelError).toBe('Excel export failed')

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(2)
            expect(service.downloadExcelFile).toHaveBeenCalledWith(
                'xlsx_12345',
                'report.xlsx'
            )
            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBe('Successfully downloaded')
        })

        it('clears stale excel state when a new conversion starts', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(getExcelState(result).excelSuccessMessage).toBe('Successfully downloaded')

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
            expect(getExcelState(result).canDownloadExcel).toBe(true)
        })

        it('ignores stale excel export failures after a newer conversion starts', async () => {
            const firstExcelExport = deferred<typeof validExcelExportResponse>()
            const service = makeMockService({
                exportToExcel: vi.fn()
                    .mockImplementationOnce(() => firstExcelExport.promise)
                    .mockResolvedValue(validExcelExportResponse),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getExcelState(result).handleExcelDownload()
            })

            await waitFor(() => expect(service.exportToExcel).toHaveBeenCalledTimes(1))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                firstExcelExport.reject(new Error('stale excel export failure'))
                await Promise.resolve()
            })

            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
            expect(getExcelState(result).isExcelDownloading).toBe(false)
            expect(service.downloadExcelFile).not.toHaveBeenCalled()
        })

        it('ignores stale excel export success after a newer conversion starts', async () => {
            const firstExcelExport = deferred<typeof validExcelExportResponse>()
            const service = makeMockService({
                exportToExcel: vi.fn()
                    .mockImplementationOnce(() => firstExcelExport.promise)
                    .mockResolvedValue(validExcelExportResponse),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getExcelState(result).handleExcelDownload()
            })

            await waitFor(() => expect(service.exportToExcel).toHaveBeenCalledTimes(1))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                firstExcelExport.resolve(validExcelExportResponse)
                await firstExcelExport.promise
            })

            expect(service.downloadExcelFile).not.toHaveBeenCalled()
            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
            expect(getExcelState(result).isExcelDownloading).toBe(false)
        })

        it('ignores stale excel download success after a newer conversion starts', async () => {
            const firstDownload = deferred<void>()
            const service = makeMockService({
                downloadExcelFile: vi.fn()
                    .mockImplementationOnce(() => firstDownload.promise)
                    .mockResolvedValue(undefined),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            act(() => {
                void getExcelState(result).handleExcelDownload()
            })

            await waitFor(() => expect(service.downloadExcelFile).toHaveBeenCalledTimes(1))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                firstDownload.resolve(undefined)
                await firstDownload.promise
            })

            expect(getExcelState(result).excelError).toBeNull()
            expect(getExcelState(result).excelSuccessMessage).toBeNull()
            expect(getExcelState(result).isExcelDownloading).toBe(false)
        })

        it('re-exports excel on repeated download clicks', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(2)
            expect(service.downloadExcelFile).toHaveBeenNthCalledWith(
                1,
                'xlsx_12345',
                'report.xlsx'
            )
            expect(service.downloadExcelFile).toHaveBeenNthCalledWith(
                2,
                'xlsx_12345',
                'report.xlsx'
            )
        })

        it('exports excel again after the first successful download', async () => {
            const service = makeMockService()
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(1)

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(2)
            expect(service.downloadExcelFile).toHaveBeenCalledTimes(2)
        })

        it('re-exports excel after a browser download failure', async () => {
            const service = makeMockService({
                downloadExcelFile: vi.fn()
                    .mockRejectedValueOnce(new Error('Failed to export'))
                    .mockResolvedValueOnce(undefined),
            })
            const { result } = renderHook(() => useConvertFlow(service))

            await act(async () => {
                await result.current.handleFileSelect(testFile)
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            await act(async () => {
                await getExcelState(result).handleExcelDownload()
            })

            expect(service.exportToExcel).toHaveBeenCalledTimes(2)
            expect(service.downloadExcelFile).toHaveBeenCalledTimes(2)
            expect(getExcelState(result).excelSuccessMessage).toBe('Successfully downloaded')
        })
    })
})
