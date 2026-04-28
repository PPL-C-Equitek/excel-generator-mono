'use client'

import { useState, type ReactNode, type DragEvent, type ChangeEvent } from 'react'

interface UploadZoneProps {
    readonly onFileSelect?: (file: File, prompt?: string) => void
    readonly onFileChange?: () => void
    readonly disabled?: boolean
    readonly footerContent?: ReactNode
    readonly resultContent?: ReactNode
    readonly selectedSchemaName?: string | null
    readonly isValidating?: boolean
    readonly isGenerating?: boolean
    readonly validationError?: string | null
}

interface ChatMessage {
    id: number
    text: string
}

function FileIcon({ className = 'h-12 w-12' }: Readonly<{ className?: string }>) {
    return (
        <svg className={className} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="4" width="28" height="36" rx="3" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" />
            <path d="M28 4L36 12H28V4Z" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" strokeLinejoin="round" />
            <rect x="13" y="20" width="18" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
            <rect x="13" y="25" width="13" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
            <rect x="13" y="30" width="15" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
        </svg>
    )
}

function AttachmentIcon() {
    return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
    )
}

function SendIcon() {
    return (
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M3.5 10L16.5 3.5L13 16.5L9.75 10.75L3.5 10Z" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function AssistantAvatar() {
    return (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-700 text-xs font-extrabold tracking-widest text-white shadow-md">
            AI
        </div>
    )
}

function UserAvatar() {
    return (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-md">
            U
        </div>
    )
}

function AttachedFileCard({ file, variant = 'light' }: Readonly<{ file: File; variant?: 'light' | 'dark' }>) {
    const isDark = variant === 'dark'

    return (
        <div className={`flex items-center gap-3 rounded-xl p-3 text-left ${isDark ? 'bg-white/15 ring-1 ring-white/20' : 'border border-gray-200 bg-white shadow-sm'}`}>
            <FileIcon className="h-10 w-10 shrink-0" />
            <div className="min-w-0 flex-1">
                <p className={`break-all text-sm font-semibold leading-snug ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    {file.name}
                </p>
                <p className={`mt-1 text-xs ${isDark ? 'text-blue-100' : 'text-gray-500'}`}>
                    {formatFileSize(file.size)}
                </p>
            </div>
            {!isDark && (
                <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
                    Attached
                </span>
            )}
        </div>
    )
}

export default function UploadZone({
    onFileSelect,
    onFileChange,
    disabled,
    footerContent,
    resultContent,
    selectedSchemaName,
    isValidating = false,
    isGenerating = false,
    validationError,
}: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [submittedFile, setSubmittedFile] = useState<File | null>(null)
    const [chatInput, setChatInput] = useState('')
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])

    const isConversationStarted = Boolean(submittedFile && (isGenerating || resultContent))
    const isValidationFeedbackVisible = Boolean(
        submittedFile &&
        selectedFile === submittedFile &&
        (isValidating || validationError)
    )
    const trimmedChatInput = chatInput.trim()

    const handleFile = (file: File) => {
        setSelectedFile(file)
        setSubmittedFile(null)
        setChatMessages([])
        setChatInput('')
        onFileChange?.()
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

    const handleReset = () => {
        setSelectedFile(null)
        setSubmittedFile(null)
        setChatMessages([])
        setChatInput('')
        onFileChange?.()
    }

    const handleSubmit = () => {
        if (!selectedFile) return
        setSubmittedFile(selectedFile)
        setChatMessages([])
        onFileSelect?.(selectedFile)
    }

    const handleFollowUpSubmit = () => {
        if (!submittedFile || trimmedChatInput.length === 0) return
        setChatMessages((messages) => [
            ...messages,
            { id: Date.now(), text: trimmedChatInput },
        ])
        onFileSelect?.(submittedFile, trimmedChatInput)
        setChatInput('')
    }

    const dropZoneBaseClassName = 'flex min-h-48 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-12 text-center transition-colors sm:p-20'
    const dropZoneStateClassName = isDragging ? 'border-red-600 bg-red-50' : 'border-gray-300 bg-gray-100'
    const dropZoneClassName = `${dropZoneBaseClassName} ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-red-600 hover:bg-red-50'} ${dropZoneStateClassName}`
    const stagedFileZoneClassName = `${dropZoneBaseClassName} ${disabled ? 'opacity-60' : ''} ${dropZoneStateClassName}`

    if (isConversationStarted) {
        return (
            <section className="flex h-screen flex-col">
                <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
                    {submittedFile && (
                        <div className="flex w-full items-start justify-end gap-3">
                            <div className="max-w-xl rounded-2xl rounded-tr-sm bg-blue-600 p-4 text-sm text-white shadow-md lg:max-w-2xl">
                                <p className="font-semibold">Generate this file.</p>
                                {selectedSchemaName && (
                                    <div className="mt-3 rounded-xl bg-white/15 px-3 py-2 text-left ring-1 ring-white/20">
                                        <p className="text-xs font-semibold uppercase tracking-widest text-blue-100">
                                            Schema context
                                        </p>
                                        <p className="mt-1 break-words text-sm font-semibold text-white">
                                            {selectedSchemaName}
                                        </p>
                                    </div>
                                )}
                                <div className="mt-3">
                                    <AttachedFileCard file={submittedFile} variant="dark" />
                                </div>
                            </div>
                            <UserAvatar />
                        </div>
                    )}

                    {resultContent ? (
                        <div className="flex w-full items-start justify-start gap-3">
                            <AssistantAvatar />
                            <div className="max-w-2xl rounded-2xl rounded-tl-sm bg-white p-4 text-sm text-gray-700 shadow-sm ring-1 ring-gray-200 lg:max-w-3xl">
                                {resultContent}
                            </div>
                        </div>
                    ) : null}

                    {chatMessages.map((message) => (
                        <div key={message.id} className="flex w-full items-start justify-end gap-3">
                            <div className="max-w-xl rounded-2xl rounded-tr-sm bg-blue-600 p-4 text-sm text-white shadow-md lg:max-w-2xl">
                                <p className="whitespace-pre-wrap">{message.text}</p>
                            </div>
                            <UserAvatar />
                        </div>
                    ))}
                </div>

                {submittedFile && resultContent ? (
                    <div className="border-t border-gray-200 bg-gray-50/95 px-4 py-4 backdrop-blur sm:px-6 lg:px-8">
                        <label htmlFor="follow-up-chat" className="sr-only">
                            Follow-up message
                        </label>
                        <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-end">
                            <textarea
                                id="follow-up-chat"
                                aria-label="Follow-up message"
                                value={chatInput}
                                onChange={(event) => setChatInput(event.target.value)}
                                disabled={disabled}
                                rows={2}
                                placeholder="Ask a follow-up question or refine the output..."
                                className="min-h-12 flex-1 resize-none rounded-2xl border border-gray-300 bg-gray-100 px-4 py-3 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                            <button
                                type="button"
                                onClick={handleFollowUpSubmit}
                                disabled={disabled || trimmedChatInput.length === 0}
                                className="inline-flex items-center justify-center gap-2 rounded-xl bg-red-700 px-5 py-3 text-sm font-bold text-white shadow-md transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Send
                                <SendIcon />
                            </button>
                        </div>
                    </div>
                ) : null}
            </section>
        )
    }

    if (selectedFile) {
        return (
            <section className="flex min-h-screen items-center justify-center px-6 py-8 lg:px-12">
                <div className="w-full max-w-3xl space-y-6">
                    <div className={stagedFileZoneClassName}>
                        <div className="w-full max-w-sm">
                            <AttachedFileCard file={selectedFile} />
                        </div>
                    </div>

                    {footerContent}

                    {isValidationFeedbackVisible && (
                        <div className={`rounded-lg border px-4 py-3 text-sm ${validationError
                            ? 'border-red-400 bg-red-50 text-red-700'
                            : 'border-gray-200 bg-gray-50 text-gray-600'
                            }`} role={validationError ? 'alert' : undefined}>
                            {validationError ? (
                                <span>{validationError}</span>
                            ) : (
                                <span className="inline-flex items-center gap-2">
                                    <span className="h-2 w-2 animate-pulse rounded-full bg-red-700" />
                                    Validating file...
                                </span>
                            )}
                        </div>
                    )}

                    <div className="flex justify-center gap-3">
                        <button
                            type="button"
                            onClick={handleReset}
                            disabled={disabled}
                            className="rounded-xl border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-600 transition hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Change File
                        </button>
                        <button
                            type="button"
                            data-testid="convert-btn"
                            onClick={handleSubmit}
                            disabled={disabled}
                            className="rounded-xl bg-red-700 px-8 py-2.5 text-sm font-bold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Generate File
                        </button>
                    </div>
                </div>
            </section>
        )
    }

    return (
        <section className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
            <div className="w-full max-w-3xl space-y-6">
                <label
                    data-testid="drop-zone"
                    onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                    aria-label="File upload drop zone"
                    className={dropZoneClassName}
                >
                    <input
                        data-testid="file-input"
                        type="file"
                        onChange={handleChange}
                        disabled={disabled}
                        className="hidden"
                    />
                    <span className="flex h-11 w-11 items-center justify-center rounded-full bg-red-700 text-white shadow-md transition">
                        <AttachmentIcon />
                    </span>
                    <span className="rounded-xl bg-red-700 px-8 py-3 font-bold text-white transition">
                        Upload File
                    </span>
                    <p className="text-sm text-gray-500">Or drop file here</p>
                </label>

                {footerContent}
            </div>
        </section>
    )
}
