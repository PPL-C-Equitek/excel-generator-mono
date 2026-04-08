'use client'

import { useState, useRef } from 'react'
import { uploadFile } from '@/lib/api'
import {
    downloadExcelFile,
    exportToCsv,
    exportToExcel,
    generateJson,
    getDownloadUrl,
} from '@/services/llm'
import { isJsonObject } from '@/utils/schemaValidator'
import { sanitizeCSVCell } from '@/utils/csvSanitizer'
import type { ILLMService } from '@/lib/ILLMService'
import type { JsonObject, JsonValue } from '@/utils/schemaValidator'

const defaultService: ILLMService = { 
    generate: generateJson, 
    exportToCsv,
    exportToExcel,
    downloadExcelFile,
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

export interface UseConvertFlowReturn {
    isConverting: boolean
    isExcelDownloading: boolean
    canDownloadExcel: boolean
    error: string | null
    excelError: string | null
    excelSuccessMessage: string | null
    outputFile: OutputFile | null
    csvMetadata: CsvMetadata | null
    handleFileSelect: (file: File) => Promise<void>
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
    const abortControllerRef = useRef<AbortController | null>(null)

    const abortPreviousRequest = (): AbortSignal => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        const controller = new AbortController()
        abortControllerRef.current = controller
        return controller.signal
    }

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

    const processCsvExport = async (out: unknown, signal: AbortSignal) => {
        if (!llmService.exportToCsv || signal.aborted) return

        try {
            const isStringEmpty = typeof out === 'string' && out.trim() === ''
            const isEmpty = out === null || isStringEmpty || 
                (Array.isArray(out) && out.length === 0) || 
                (typeof out === 'object' && out !== null && Object.keys(out).length === 0)
                
            if (isEmpty) {
                throw new Error("The converted data is empty or invalid, so it can't be exported.")
            }

            const sanitizedJSON = sanitizeCSVCell(out) as JsonValue
            const csvResult = await llmService.exportToCsv(sanitizedJSON)
            
            if (!signal.aborted) {
                if (csvResult.file_id?.startsWith('csv_')) {
                    setCsvMetadata({ file_id: csvResult.file_id })
                } else {
                    throw new Error('The export result is invalid. Please try again.')
                }
            }
        } catch (csvErr: unknown) {
            handleProcessError(csvErr, 'CSV Export failed', signal)
        }
    }

    const processConversion = async (uploadResult: JsonObject, file: File, signal: AbortSignal) => {
        try {
            const llmResult = await llmService.generate(uploadResult)
            if (signal.aborted) return

            setGeneratedOutput(llmResult.output_json)
            setOutputFile(parseOutputFile(uploadResult, file))

            await processCsvExport(llmResult.output_json, signal)
        } catch (err: unknown) {
            handleProcessError(err, 'Conversion failed', signal)
        } finally {
            if (!signal.aborted) {
                setIsConverting(false)
            }
        }
    }

    const handleFileSelect = async (file: File): Promise<void> => {
        const signal = abortPreviousRequest()

        setError(null)
        setExcelError(null)
        setExcelSuccessMessage(null)
        setOutputFile(null)
        setCsvMetadata(null)
        setGeneratedOutput(null)
        setIsExcelDownloading(false)
        setIsConverting(true)

        const uploadResult = await processUpload(file, signal)
        if (!uploadResult) return

        await processConversion(uploadResult, file, signal)
    }

    const handleExcelDownload = async (): Promise<void> => {
        if (
            !generatedOutput ||
            !outputFile ||
            isExcelDownloading ||
            !llmService.exportToExcel ||
            !llmService.downloadExcelFile
        ) {
            return
        }

        setExcelError(null)
        setExcelSuccessMessage(null)
        setIsExcelDownloading(true)

        try {
            const excelResult = await llmService.exportToExcel(generatedOutput)
            await llmService.downloadExcelFile(
                excelResult.file_id,
                getExcelDownloadFilename(outputFile.filename)
            )
            setExcelError(null)
            setExcelSuccessMessage('Successfully downloaded')
        } catch (err: unknown) {
            setExcelSuccessMessage(null)
            setExcelError(err instanceof Error ? err.message : 'Failed to export')
        } finally {
            setIsExcelDownloading(false)
        }
    }

    const canDownloadExcel = (
        generatedOutput !== null &&
        !!llmService.exportToExcel &&
        !!llmService.downloadExcelFile
    )

    return {
        isConverting,
        isExcelDownloading,
        canDownloadExcel,
        error,
        excelError,
        excelSuccessMessage,
        outputFile,
        csvMetadata,
        handleFileSelect,
        handleExcelDownload,
        llmService
    }
}
