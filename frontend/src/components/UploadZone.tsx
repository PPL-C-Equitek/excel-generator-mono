'use client'

import { useState, useRef, DragEvent, ChangeEvent } from 'react'

interface UploadZoneProps {
    onFileSelect?: (file: File) => void
}

export default function UploadZone({ onFileSelect }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    const handleFile = (file: File) => {
        setSelectedFile(file.name)
        onFileSelect?.(file)
    }

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
    }

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
    }

    return (
        <div
            data-testid="drop-zone"
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-20 flex flex-col items-center justify-center gap-3 transition-colors
        ${isDragging ? 'border-red-600 bg-red-50' : 'border-gray-300 bg-gray-100'}`}
        >
            <input
                data-testid="file-input"
                type="file"
                ref={inputRef}
                onChange={handleChange}
                className="hidden"
            />
            <button
                onClick={() => inputRef.current?.click()}
                className="bg-red-700 text-white font-bold px-8 py-3 rounded-xl hover:bg-red-800 transition"
            >
                Upload File
            </button>
            {selectedFile
                ? <p className="text-gray-600 text-sm">{selectedFile}</p>
                : <p className="text-gray-400 text-sm">Or drop file here</p>
            }
        </div>
    )
}