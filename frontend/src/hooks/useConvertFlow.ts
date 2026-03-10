'use client'

import { useState, useRef } from 'react'
import { uploadFile } from '@/lib/api'
import { generateJson, exportToCsv, getDownloadUrl } from '@/services/llm'
import { isJsonObject } from '@/utils/schemaValidator'
import { sanitizeCSVCell } from '@/utils/csvSanitizer'
import type { ILLMService } from '@/lib/ILLMService'
import type { JsonObject, JsonValue } from '@/utils/schemaValidator'

const defaultService: ILLMService = { 
    generate: generateJson, 
    exportToCsv,
    getDownloadUrl
}

export interface OutputFile {
    filename: string
    format: string
    size: number
}

function parseOutputFile(uploadResult: JsonObject, fallbackFile: File): OutputFile {
    const rawFilename = uploadResult.filename
    const inputName = typeof rawFilename === 'string' && rawFilename.trim().length > 0
        ? rawFilename
        : fallbackFile.name
    const baseName = inputName.replace(/\.[^/.]+$/, '')

    const rawSize = uploadResult.size
    let parsedSize = fallbackFile.size
    if (typeof rawSize === 'number') {
        parsedSize = rawSize
    } else if (typeof rawSize === 'string') {
        parsedSize = Number(rawSize)
    }

    return {
        filename: `${baseName}.xlsx`,
        format: 'xlsx',
        size: parsedSize || 0,
    }
}

export interface CsvMetadata {
    file_id: string;
}

export interface UseConvertFlowReturn {
    isConverting: boolean
    error: string | null
    outputFile: OutputFile | null
    csvMetadata: CsvMetadata | null
    handleFileSelect: (file: File) => Promise<void>
    llmService: ILLMService
}

export function useConvertFlow(
    llmService: ILLMService = defaultService
): UseConvertFlowReturn {
    const [isConverting, setIsConverting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [outputFile, setOutputFile] = useState<OutputFile | null>(null)
    const [csvMetadata, setCsvMetadata] = useState<CsvMetadata | null>(null)
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
                setError('Respons upload tidak valid')
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
                throw new Error('Data tidak valid atau kosong, tidak dapat mengekspor CSV')
            }

            const sanitizedJSON = sanitizeCSVCell(out) as JsonValue
            const csvResult = await llmService.exportToCsv(sanitizedJSON)
            
            if (!signal.aborted) {
                if (csvResult.file_id?.startsWith('csv_')) {
                    setCsvMetadata({ file_id: csvResult.file_id })
                } else {
                    throw new Error('ID File CSV tidak valid')
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
        setOutputFile(null)
        setCsvMetadata(null)
        setIsConverting(true)

        const uploadResult = await processUpload(file, signal)
        if (!uploadResult) return

        await processConversion(uploadResult, file, signal)
    }

    return { isConverting, error, outputFile, csvMetadata, handleFileSelect, llmService }
}
