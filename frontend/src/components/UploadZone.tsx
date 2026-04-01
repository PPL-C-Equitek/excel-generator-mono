'use client'

import { useState, DragEvent, ChangeEvent } from 'react'

interface UploadZoneProps {
    readonly onFileSelect?: (file: File) => void
    readonly disabled?: boolean
}

function FileIcon() {
    return (
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="4" width="28" height="36" rx="3" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" />
            <path d="M28 4L36 12H28V4Z" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" strokeLinejoin="round" />
            <rect x="13" y="20" width="18" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
            <rect x="13" y="25" width="13" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
            <rect x="13" y="30" width="15" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
        </svg>
    )
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadZone({ onFileSelect, disabled }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)

    const handleFile = (file: File) => {
        setSelectedFile(file)
    }

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
        e.target.value = ''
    }

    const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
        e.preventDefault()
        setIsDragging(false)
        if (disabled) return
        const file = e.dataTransfer.files?.[0]
        if (file) handleFile(file)
    }

    const handleConvert = () => {
        if (selectedFile) {
            onFileSelect?.(selectedFile)
        }
    }

    const handleReset = () => {
        setSelectedFile(null)
    }

    if (selectedFile) {
        return (
            <div className="flex flex-col items-center gap-6 py-8 animate-fadeIn">
                {/* File card */}
                <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white shadow-md p-6 flex flex-col items-center gap-4">
                    <FileIcon />
                    <div className="text-center">
                        <p className="font-semibold text-gray-900 text-base break-all leading-snug">
                            {selectedFile.name}
                        </p>
                        <p className="text-sm text-gray-400 mt-1">
                            {formatFileSize(selectedFile.size)}
                        </p>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleReset}
                        disabled={disabled}
                        className="px-5 py-2.5 rounded-xl border border-gray-300 text-sm font-medium text-gray-600 hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Change File
                    </button>
                    <button
                        data-testid="convert-btn"
                        onClick={handleConvert}
                        disabled={disabled}
                        className="px-8 py-2.5 rounded-xl bg-red-700 text-white font-bold text-sm hover:bg-red-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Convert
                    </button>
                </div>

                <style>{`
                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(12px); }
                        to   { opacity: 1; transform: translateY(0); }
                    }
                    .animate-fadeIn {
                        animation: fadeIn 0.3s ease both;
                    }
                `}</style>
            </div>
        )
    }

    // Default upload zone
    return (
        <label
            data-testid="drop-zone"
            onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            aria-label="File upload drop zone"
            className={`border-2 border-dashed rounded-lg p-20 flex flex-col items-center justify-center gap-3 transition-colors
                ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}
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
                Upload File
            </span>
            <p className="text-gray-400 text-sm">Or drop file here</p>
        </label>
    )
}