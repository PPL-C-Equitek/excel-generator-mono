'use client'

import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { uploadFile } from '@/lib/api'

interface UploadZoneProps {
    readonly onFileSelect?: (file: File) => void
}

export default function UploadZone({ onFileSelect }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    const handleFile = async (file: File) => {
        setSelectedFile(file.name)
        setIsLoading(true)
        setError(null)
        try {
            await uploadFile(file)
            onFileSelect?.(file)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed')
        } finally {
            setIsLoading(false)
        }
    }

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
    }

    const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
    }

    return (
        <label
            data-testid="drop-zone"
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            aria-label="File upload drop zone"
            className={`border-2 border-dashed rounded-lg p-20 flex flex-col items-center justify-center gap-3 transition-colors cursor-pointer
                ${isDragging ? 'border-red-600 bg-red-50' : 'border-gray-300 bg-gray-100'}`}
        >
            <input
                data-testid="file-input"
                type="file"
                ref={inputRef}
                onChange={handleChange}
                disabled={isLoading}
                className="hidden"
            />
            <span
                className={`bg-red-700 text-white font-bold px-8 py-3 rounded-xl transition pointer-events-none
                    ${isLoading ? 'opacity-50' : 'hover:bg-red-800'}`}
            >
                {isLoading ? 'Uploading...' : 'Upload File'}
            </span>

            {error && (
                <p className="text-red-500 text-sm">{error}</p>
            )}

            {!error && (selectedFile
                ? <p className="text-gray-600 text-sm">{selectedFile}</p>
                : <p className="text-gray-400 text-sm">Or drop file here</p>
            )}
        </label>
    )
}