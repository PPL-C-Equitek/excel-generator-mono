'use client'

import { useState } from 'react'
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

    const handleFileSelect = async (file: File): Promise<void> => {
        setError(null)
        setOutputFile(null)
        setIsConverting(true)

        let uploadResult: JsonValue
        try {
            const raw: unknown = await uploadFile(file)
            if (!isJsonObjectOrArray(raw)) {
                setError('Respons upload tidak valid')
                setIsConverting(false)
                return
            }
            uploadResult = raw
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed')
            setIsConverting(false)
            return
        }

        try {
            await llmService.generate(uploadResult)
            const record = uploadResult as Record<string, unknown>
            const inputName = String(record.filename ?? file.name)
            const baseName = inputName.replace(/\.[^/.]+$/, '')
            setOutputFile({
                filename: `${baseName}.xlsx`,
                format: 'xlsx',
                size: Number(record.size ?? 0),
            })
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Conversion failed')
        } finally {
            setIsConverting(false)
        }
    }

    return { isConverting, error, outputFile, handleFileSelect }
}
