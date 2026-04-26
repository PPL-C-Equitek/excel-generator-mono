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

        const requestId = conversionRequestIdRef.current
        const csvOutput = generatedOutput
        const csvFilename = outputFile.filename.replace(/\.[^/.]+$/, '') + '.csv'
        const canUseSessionDownload = Boolean(
            generatedSessionId &&
            generatedOutputId &&
            llmService.downloadSessionOutputCsvFile
        )

        if (!canUseSessionDownload && isExportOutputEmpty(csvOutput)) {
            setError("The converted data is empty or invalid, so it can't be exported.")
            return
        }

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
        const excelOutput = generatedOutput
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
