'use client'

import { useState, useRef } from 'react'
import { uploadFile } from '@/lib/api'
import { generateJson } from '@/services/llm'
import { isJsonObject } from '@/utils/schemaValidator'
import type { ILLMService } from '@/lib/ILLMService'
import type { JsonObject } from '@/utils/schemaValidator'

const defaultService: ILLMService = { generate: generateJson }

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

export interface UseConvertFlowReturn {
    isConverting: boolean
    error: string | null
    outputFile: OutputFile | null
    handleFileSelect: (file: File) => Promise<void>
}

export function useConvertFlow(
    llmService: ILLMService = defaultService
): UseConvertFlowReturn {
    const [isConverting, setIsConverting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [outputFile, setOutputFile] = useState<OutputFile | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)

    const handleFileSelect = async (file: File): Promise<void> => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }
        const abortController = new AbortController()
        abortControllerRef.current = abortController

        setError(null)
        setOutputFile(null)
        setIsConverting(true)

        let uploadResult: JsonObject
        try {
            const raw: unknown = await uploadFile(file, { signal: abortController.signal })
            if (abortController.signal.aborted) return
            if (!isJsonObject(raw)) {
                setError('Respons upload tidak valid')
                setIsConverting(false)
                return
            }
            uploadResult = raw
        } catch (err: unknown) {
            if (abortController.signal.aborted) return
            if (err instanceof DOMException && err.name === 'AbortError') return
            setError(err instanceof Error ? err.message : 'Upload failed')
            setIsConverting(false)
            return
        }

        try {
            await llmService.generate(uploadResult)
            if (abortController.signal.aborted) return

            const parsedOutput = parseOutputFile(uploadResult, file)
            setOutputFile(parsedOutput)
        } catch (err: unknown) {
            if (abortController.signal.aborted) return
            setError(err instanceof Error ? err.message : 'Conversion failed')
        } finally {
            if (!abortController.signal.aborted) {
                setIsConverting(false)
            }
        }
    }

    return { isConverting, error, outputFile, handleFileSelect }
}
