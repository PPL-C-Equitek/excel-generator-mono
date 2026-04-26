'use client'

import { useState, useRef } from 'react'
import { uploadFile } from '@/lib/api'
import {
    downloadCsvFile,
    downloadExcelFile,
    downloadSessionOutputCsvFile,
    downloadSessionOutputExcelFile,
    exportToCsv,
    exportToExcel,
    generateJson,
    getDownloadUrl,
} from '@/services/llm'
import { isJsonObject } from '@/utils/schemaValidator'
import { sanitizeCSVCell } from '@/utils/csvSanitizer'
import type { ILLMService } from '@/lib/ILLMService'
import type { JsonObject, JsonValue } from '@/utils/schemaValidator'
import { FILE_TOO_LARGE_MESSAGE, MAX_UPLOAD_SIZE_BYTES } from '@/constants/upload'

const defaultService: ILLMService = {
    generate: generateJson,
    exportToCsv,
    downloadCsvFile,
    exportToExcel,
    downloadExcelFile,
    downloadSessionOutputCsvFile,
    downloadSessionOutputExcelFile,
    getDownloadUrl
}

export interface OutputFile {
    filename: string
    format: string
    size: number
}

function parseOutputFile(uploadResult: JsonObject, fallbackFile: File): OutputFile {
    const directFilename = uploadResult.filename
    const documentInfo = uploadResult.document_info
    const nestedFilename = isJsonObject(documentInfo) ? documentInfo.filename : undefined

    const inputName = (
        (typeof directFilename === 'string' && directFilename.trim().length > 0 && directFilename) ||
        (typeof nestedFilename === 'string' && nestedFilename.trim().length > 0 && nestedFilename) ||
        fallbackFile.name
    )

    const extensionMatch = /\.([^.]+)$/.exec(inputName)
    const inferredFormat = extensionMatch?.[1]?.toLowerCase() || fallbackFile.type.split('/')[1] || 'bin'

    const rawSize = uploadResult.size
    let parsedSize = fallbackFile.size
    if (typeof rawSize === 'number') {
        parsedSize = rawSize
    } else if (typeof rawSize === 'string') {
        parsedSize = Number(rawSize)
    }

    return {
        filename: inputName,
        format: inferredFormat,
        size: parsedSize || 0,
    }
}

export interface CsvMetadata {
    file_id: string;
}

type ScalarCell = string | number | boolean | null

const DEFAULT_EXCEL_TABLE_NAME = 'Sheet1'
const DEFAULT_VALUE_HEADER = 'value'

function toScalarCell(value: unknown): ScalarCell {
    if (
        value === null ||
        typeof value === 'string' ||
        typeof value === 'number' ||
        typeof value === 'boolean'
    ) {
        return value
    }

    try {
        return JSON.stringify(value)
    } catch {
        return '[Unserializable Value]'
    }
}

function normalizeHeaders(rawHeaders: unknown[]): string[] {
    if (rawHeaders.length === 0) {
        return [DEFAULT_VALUE_HEADER]
    }

    const counts = new Map<string, number>()

    return rawHeaders.map((rawHeader, index) => {
        const trimmed =
            typeof rawHeader === 'string' && rawHeader.trim().length > 0
                ? rawHeader.trim()
                : `column_${index + 1}`

        const key = trimmed.toLowerCase()
        const count = counts.get(key) ?? 0
        counts.set(key, count + 1)

        return count === 0 ? trimmed : `${trimmed}_${count + 1}`
    })
}

function mapArrayRowToObject(row: unknown[], headers: string[]): JsonObject {
    const mappedRow: JsonObject = {}

    headers.forEach((header, index) => {
        const cell = row[index] as JsonValue | undefined
        mappedRow[header] = toScalarCell(cell ?? null)
    })

    return mappedRow
}

function mapObjectRowToObject(row: JsonObject, headers: string[]): JsonObject {
    const mappedRow: JsonObject = {}

    headers.forEach((header) => {
        const cell = row[header] as JsonValue | undefined
        mappedRow[header] = toScalarCell(cell ?? null)
    })

    return mappedRow
}

function mapUnknownRowToObject(row: unknown, headers: string[]): JsonObject {
    const mappedRow: JsonObject = {}

    headers.forEach((header, index) => {
        if (index === 0) {
            mappedRow[header] = toScalarCell(row)
            return
        }

        mappedRow[header] = null
    })

    return mappedRow
}

function buildRowsFromGeneratedOutputRows(rows: unknown[], headers: string[]): JsonObject[] {
    return rows.map((row) => {
        if (Array.isArray(row)) {
            return mapArrayRowToObject(row, headers)
        }

        if (isJsonObject(row)) {
            return mapObjectRowToObject(row, headers)
        }

        return mapUnknownRowToObject(row, headers)
    })
}

function inferHeadersAndRowsFromRowsArray(rows: unknown[]): { headers: string[]; rows: JsonObject[] } {
    if (rows.length > 0 && rows.every((row) => Array.isArray(row))) {
        const maxColumns = rows.reduce(
            (max, row) => Math.max(max, (row as unknown[]).length),
            0
        )
        const headers = normalizeHeaders(
            Array.from({ length: maxColumns }, (_, index) => `column_${index + 1}`)
        )
        return {
            headers,
            rows: buildRowsFromGeneratedOutputRows(rows, headers),
        }
    }

    if (rows.length > 0 && rows.every((row) => isJsonObject(row))) {
        const collectedHeaders = Array.from(
            new Set(
                rows.flatMap((row) => Object.keys(row))
            )
        )
        const headers = normalizeHeaders(collectedHeaders)
        return {
            headers,
            rows: buildRowsFromGeneratedOutputRows(rows, headers),
        }
    }

    const headers = [DEFAULT_VALUE_HEADER]
    return {
        headers,
        rows: rows.map((value) => ({
            [DEFAULT_VALUE_HEADER]: toScalarCell(value),
        })),
    }
}

function inferHeadersAndRowsFromOutput(output: JsonValue): { headers: string[]; rows: JsonObject[] } {
    if (isJsonObject(output)) {
        const headers = normalizeHeaders(Object.keys(output))
        return {
            headers,
            rows: [mapObjectRowToObject(output, headers)],
        }
    }

    if (Array.isArray(output)) {
        return inferHeadersAndRowsFromRowsArray(output)
    }

    return {
        headers: [DEFAULT_VALUE_HEADER],
        rows: [{ [DEFAULT_VALUE_HEADER]: toScalarCell(output) }],
    }
}

function buildContentDataFromOutput(output: JsonValue): JsonObject[] {
    if (isJsonObject(output)) {
        const directHeaders = output.headers
        const directRows = output.rows
        if (Array.isArray(directHeaders) && Array.isArray(directRows)) {
            const headers = normalizeHeaders(directHeaders)
            return [
                {
                    table_name: DEFAULT_EXCEL_TABLE_NAME,
                    headers,
                    rows: buildRowsFromGeneratedOutputRows(directRows, headers),
                },
            ]
        }

        const entries = Object.entries(output)
        const hasSheetLikeEntries =
            entries.length > 0 && entries.every(([, value]) => Array.isArray(value))
        if (hasSheetLikeEntries) {
            return entries.map(([sheetName, value], index) => {
                const rowsArray = value as unknown[]
                const { headers, rows } = inferHeadersAndRowsFromRowsArray(rowsArray)
                const tableName =
                    typeof sheetName === 'string' && sheetName.trim().length > 0
                        ? sheetName.trim()
                        : `Sheet${index + 1}`

                return {
                    table_name: tableName,
                    headers,
                    rows,
                }
            })
        }
    }

    const { headers, rows } = inferHeadersAndRowsFromOutput(output)
    return [
        {
            table_name: DEFAULT_EXCEL_TABLE_NAME,
            headers,
            rows,
        },
    ]
}

function isCanonicalExcelExportPayload(output: JsonValue): output is JsonObject {
    if (!isJsonObject(output)) {
        return false
    }

    return (
        isJsonObject(output.document_info) &&
        isJsonObject(output.summary) &&
        Array.isArray(output.content_data)
    )
}

function resolveSourceType(uploadResult: JsonObject | null, output: OutputFile): 'Excel' | 'PDF' {
    const documentInfo = uploadResult?.document_info
    const sourceType = isJsonObject(documentInfo) ? documentInfo.source_type : undefined

    if (typeof sourceType === 'string') {
        const normalized = sourceType.trim().toLowerCase()
        if (normalized === 'excel') return 'Excel'
        if (normalized === 'pdf') return 'PDF'
    }

    return output.format === 'pdf' ? 'PDF' : 'Excel'
}

function resolveFilename(uploadResult: JsonObject | null, output: OutputFile): string {
    const documentInfo = uploadResult?.document_info
    const nestedFilename = isJsonObject(documentInfo) ? documentInfo.filename : undefined
    const directFilename = uploadResult?.filename

    if (typeof nestedFilename === 'string' && nestedFilename.trim().length > 0) {
        return nestedFilename.trim()
    }

    if (typeof directFilename === 'string' && directFilename.trim().length > 0) {
        return directFilename.trim()
    }

    return output.filename
}

function buildTabularExportPayload(
    generatedOutput: JsonValue,
    uploadResult: JsonObject | null,
    output: OutputFile
): JsonValue {
    if (isCanonicalExcelExportPayload(generatedOutput)) {
        return generatedOutput
    }

    const contentData = buildContentDataFromOutput(generatedOutput)
    const { totalRows, totalColumns } = contentData.reduce<{ totalRows: number; totalColumns: number }>(
        (acc, table) => {
            const rowCount = (table.rows as unknown[]).length
            const columnCount = (table.headers as unknown[]).length

            return {
                totalRows: acc.totalRows + rowCount,
                totalColumns: Math.max(acc.totalColumns, columnCount),
            }
        },
        { totalRows: 0, totalColumns: 0 }
    )

    return {
        document_info: {
            source_type: resolveSourceType(uploadResult, output),
            filename: resolveFilename(uploadResult, output),
        },
        summary: {
            total_tables: contentData.length,
            total_rows: totalRows,
            total_columns: totalColumns,
        },
        content_data: contentData,
    }
}

function getExcelDownloadFilename(baseFilename: string): string {
    return baseFilename.replace(/\.[^/.]+$/, '') + '.xlsx'
}

function isExportOutputEmpty(output: unknown): boolean {
    const isStringEmpty = typeof output === 'string' && output.trim() === ''
    return output === null || isStringEmpty ||
        (Array.isArray(output) && output.length === 0) ||
        (typeof output === 'object' && output !== null && Object.keys(output).length === 0)
}

export interface UseConvertFlowReturn {
    isConverting: boolean
    isExcelDownloading: boolean
    canDownloadCsv: boolean
    canDownloadExcel: boolean
    error: string | null
    excelError: string | null
    excelSuccessMessage: string | null
    outputFile: OutputFile | null
    csvMetadata: CsvMetadata | null
    handleFileSelect: (file: File, customSchemaId?: string | null) => Promise<void>
    handleCsvDownload: () => Promise<void>
    handleExcelDownload: () => Promise<void>
    llmService: ILLMService
}

export function useConvertFlow(
    llmService: ILLMService = defaultService
): UseConvertFlowReturn {
    const [isConverting, setIsConverting] = useState(false)
    const [isExcelDownloading, setIsExcelDownloading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [excelError, setExcelError] = useState<string | null>(null)
    const [excelSuccessMessage, setExcelSuccessMessage] = useState<string | null>(null)
    const [outputFile, setOutputFile] = useState<OutputFile | null>(null)
    const [uploadResultForExport, setUploadResultForExport] = useState<JsonObject | null>(null)
    const [csvMetadata, setCsvMetadata] = useState<CsvMetadata | null>(null)
    const [generatedOutput, setGeneratedOutput] = useState<JsonValue | null>(null)
    const [generatedSessionId, setGeneratedSessionId] = useState<string | null>(null)
    const [generatedOutputId, setGeneratedOutputId] = useState<string | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)
    const conversionRequestIdRef = useRef(0)

    const abortPreviousRequest = (): AbortSignal => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        const controller = new AbortController()
        abortControllerRef.current = controller
        return controller.signal
    }

    const getActiveSignal = (): AbortSignal | undefined =>
        abortControllerRef.current?.signal

    const handleProcessError = (err: unknown, defaultMsg: string, signal: AbortSignal) => {
        if (signal.aborted) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : defaultMsg)
        setIsConverting(false)
    }

    const processUpload = async (file: File, signal: AbortSignal): Promise<JsonObject | null> => {
        try {
            const raw: unknown = await uploadFile(file, { signal })
            if (signal.aborted) return null
            if (!isJsonObject(raw)) {
                setError('The server returned an invalid upload response.')
                setIsConverting(false)
                return null
            }
            return raw
        } catch (err: unknown) {
            handleProcessError(err, 'Upload failed', signal)
            return null
        }
    }

    const resetConversionState = () => {
        setError(null)
        setExcelError(null)
        setExcelSuccessMessage(null)
        setOutputFile(null)
        setUploadResultForExport(null)
        setCsvMetadata(null)
        setGeneratedOutput(null)
        setGeneratedSessionId(null)
        setGeneratedOutputId(null)
        setIsExcelDownloading(false)
    }

    const processConversion = async (
        uploadResult: JsonObject,
        file: File,
        signal: AbortSignal,
        customSchemaId?: string | null
    ) => {
        try {
            const llmResult =
                typeof customSchemaId === 'string' && customSchemaId.length > 0
                    ? await llmService.generate(uploadResult, customSchemaId, signal)
                    : await llmService.generate(uploadResult, undefined, signal)
            if (signal.aborted) return

            setGeneratedOutput(llmResult.output_json)
            setGeneratedSessionId(llmResult.session_id ?? null)
            setGeneratedOutputId(llmResult.output_id ?? null)
            setUploadResultForExport(uploadResult)
            setOutputFile(parseOutputFile(uploadResult, file))
        } catch (err: unknown) {
            handleProcessError(err, 'Conversion failed', signal)
        } finally {
            if (!signal.aborted) {
                setIsConverting(false)
            }
        }
    }

    const handleFileSelect = async (
        file: File,
        customSchemaId?: string | null
    ): Promise<void> => {
        conversionRequestIdRef.current += 1
        const signal = abortPreviousRequest()

        resetConversionState()

        if (file.size > MAX_UPLOAD_SIZE_BYTES) {
            setError(FILE_TOO_LARGE_MESSAGE)
            setIsConverting(false)
            return
        }

        setIsConverting(true)

        const uploadResult = await processUpload(file, signal)
        if (!uploadResult) return

        await processConversion(uploadResult, file, signal, customSchemaId)
    }

    const handleCsvDownload = async (): Promise<void> => {
        if (
            !outputFile ||
            (!llmService.downloadSessionOutputCsvFile &&
                (!llmService.exportToCsv || !llmService.downloadCsvFile))
        ) {
            return
        }

        const canUseSessionDownload = Boolean(
            generatedSessionId &&
            generatedOutputId &&
            llmService.downloadSessionOutputCsvFile
        )

        if (isExportOutputEmpty(generatedOutput)) {
            setError("The converted data is empty or invalid, so it can't be exported.")
            return
        }

        const nonEmptyOutput = generatedOutput as JsonValue

        const requestId = conversionRequestIdRef.current
        const csvOutput = buildTabularExportPayload(
            nonEmptyOutput,
            uploadResultForExport,
            outputFile
        )
        const csvFilename = outputFile.filename.replace(/\.[^/.]+$/, '') + '.csv'

        try {
            if (
                canUseSessionDownload &&
                generatedSessionId &&
                generatedOutputId &&
                llmService.downloadSessionOutputCsvFile
            ) {
                await llmService.downloadSessionOutputCsvFile(
                    generatedSessionId,
                    generatedOutputId,
                    csvFilename
                )
                return
            }

            let csvResult = csvMetadata

            if (!csvResult) {
                if (!llmService.exportToCsv) {
                    return
                }
                const sanitizedJSON = sanitizeCSVCell(csvOutput) as JsonValue
                csvResult = await llmService.exportToCsv(
                    sanitizedJSON,
                    getActiveSignal()
                )

                if (requestId !== conversionRequestIdRef.current) {
                    return
                }

                if (csvResult.file_id?.startsWith('csv_')) {
                    setCsvMetadata({ file_id: csvResult.file_id })
                } else {
                    throw new Error('The export result is invalid. Please try again.')
                }
            }

            if (!llmService.downloadCsvFile) {
                return
            }
            await llmService.downloadCsvFile(csvResult.file_id, csvFilename)
        } catch (csvErr: unknown) {
            if (requestId !== conversionRequestIdRef.current) {
                return
            }
            setError(csvErr instanceof Error ? csvErr.message : 'CSV Export failed')
        }
    }

    const handleExcelDownload = async (): Promise<void> => {
        if (
            !outputFile ||
            isExcelDownloading ||
            (
                !llmService.downloadSessionOutputExcelFile &&
                (!generatedOutput ||
                    !llmService.exportToExcel ||
                    !llmService.downloadExcelFile)
            )
        ) {
            return
        }

        const requestId = conversionRequestIdRef.current
        const excelOutput = buildTabularExportPayload(
            generatedOutput,
            uploadResultForExport,
            outputFile
        )
        const excelFilename = getExcelDownloadFilename(outputFile.filename)
        const canUseSessionDownload = Boolean(
            generatedSessionId &&
            generatedOutputId &&
            llmService.downloadSessionOutputExcelFile
        )

        setExcelError(null)
        setExcelSuccessMessage(null)
        setIsExcelDownloading(true)

        try {
            if (
                canUseSessionDownload &&
                generatedSessionId &&
                generatedOutputId &&
                llmService.downloadSessionOutputExcelFile
            ) {
                await llmService.downloadSessionOutputExcelFile(
                    generatedSessionId,
                    generatedOutputId,
                    excelFilename
                )
            } else {
                if (!generatedOutput || !llmService.exportToExcel || !llmService.downloadExcelFile) {
                    return
                }
                const excelResult = await llmService.exportToExcel(
                    excelOutput,
                    getActiveSignal()
                )

                if (requestId !== conversionRequestIdRef.current) {
                    return
                }

                await llmService.downloadExcelFile(
                    excelResult.file_id,
                    excelFilename
                )
            }

            if (requestId !== conversionRequestIdRef.current) {
                return
            }

            setExcelError(null)
            setExcelSuccessMessage('Successfully downloaded')
        } catch (err: unknown) {
            if (requestId !== conversionRequestIdRef.current) {
                return
            }
            setExcelSuccessMessage(null)
            setExcelError(err instanceof Error ? err.message : 'Failed to export')
        } finally {
            if (requestId === conversionRequestIdRef.current) {
                setIsExcelDownloading(false)
            }
        }
    }

    const canDownloadCsv = (
        generatedOutput !== null &&
        (
            !!llmService.downloadSessionOutputCsvFile ||
            (!!llmService.exportToCsv && !!llmService.downloadCsvFile)
        )
    )

    const canDownloadExcel = (
        generatedOutput !== null &&
        (
            !!llmService.downloadSessionOutputExcelFile ||
            (!!llmService.exportToExcel && !!llmService.downloadExcelFile)
        )
    )

    return {
        isConverting,
        isExcelDownloading,
        canDownloadCsv,
        canDownloadExcel,
        error,
        excelError,
        excelSuccessMessage,
        outputFile,
        csvMetadata,
        handleFileSelect,
        handleCsvDownload,
        handleExcelDownload,
        llmService
    }
}
