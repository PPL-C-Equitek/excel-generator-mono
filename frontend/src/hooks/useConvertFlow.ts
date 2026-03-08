'use client'

import { useState, useRef } from 'react'
import { uploadFile } from '@/lib/api'
import { generateJson } from '@/services/llm'
import { isJsonObjectOrArray } from '@/utils/schemaValidator'
import type { ILLMService } from '@/lib/ILLMService'
import type { JsonValue } from '@/utils/schemaValidator'

const defaultService: ILLMService = { generate: generateJson }

export interface OutputFile {
    filename: string
    format: string
    size: number
}

function parseOutputFile(uploadResult: JsonValue, fallbackFile: File): OutputFile {
    const record = (!Array.isArray(uploadResult) && uploadResult !== null && typeof uploadResult === 'object')
        ? (uploadResult as Record<string, unknown>)
        : null

    const rawFilename = record?.filename
    const inputName = typeof rawFilename === 'string' && rawFilename.trim().length > 0
        ? rawFilename
        : fallbackFile.name
    const baseName = inputName.replace(/\.[^/.]+$/, '')

    const rawSize = record?.size
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
    const requestIdRef = useRef<number>(0)

    const handleFileSelect = async (file: File): Promise<void> => {
        requestIdRef.current += 1
        const currentRequestId = requestIdRef.current

        setError(null)
        setOutputFile(null)
        setIsConverting(true)

        let uploadResult: JsonValue
        try {
            const raw: unknown = await uploadFile(file)
            if (currentRequestId !== requestIdRef.current) return
            if (!isJsonObjectOrArray(raw)) {
                setError('Respons upload tidak valid')
                setIsConverting(false)
                return
            }
            uploadResult = raw
        } catch (err) {
            if (currentRequestId !== requestIdRef.current) return
            setError(err instanceof Error ? err.message : 'Upload failed')
            setIsConverting(false)
            return
        }

        try {
            await llmService.generate(uploadResult)
            if (currentRequestId !== requestIdRef.current) return

            const parsedOutput = parseOutputFile(uploadResult, file)
            setOutputFile(parsedOutput)
        } catch (err) {
            if (currentRequestId !== requestIdRef.current) return
            setError(err instanceof Error ? err.message : 'Conversion failed')
        } finally {
            if (currentRequestId === requestIdRef.current) {
                setIsConverting(false)
            }
        }
    }

    return { isConverting, error, outputFile, handleFileSelect }
}
