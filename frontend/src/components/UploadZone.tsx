'use client'

import { useState, DragEvent, ChangeEvent } from 'react'

interface UploadZoneProps {
    readonly onFileSelect?: (file: File) => void
    readonly disabled?: boolean
}

export default function UploadZone({ onFileSelect, disabled }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)

    const handleFile = (file: File) => {
        setSelectedFile(file.name)
        onFileSelect?.(file)
    }

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
        e.target.value = '' // allow re-selecting same file
    }

    const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
        e.preventDefault()
        setIsDragging(false)
        if (disabled) return
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
    }

    return (
        <label
            data-testid="drop-zone"
            onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            aria-label="File upload drop zone"
            className={`border-2 border-dashed rounded-lg p-20 flex flex-col items-center justify-center gap-3 transition-colors ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}
                ${isDragging ? 'border-red-600 bg-red-50' : 'border-gray-300 bg-gray-100'}`}
        >
            <input
                data-testid="file-input"
                type="file"
                onChange={handleChange}
                disabled={disabled}
                className="hidden"
            />
            <span
                className={`bg-red-700 text-white font-bold px-8 py-3 rounded-xl transition pointer-events-none
                    ${disabled ? 'opacity-50' : 'hover:bg-red-800'}`}
            >
                {selectedFile ? 'Change File' : 'Upload File'}
            </span>

            {selectedFile
                ? <p className="text-gray-600 text-sm">{selectedFile}</p>
                : <p className="text-gray-400 text-sm">Or drop file here</p>
            }
        </label>
    )
}