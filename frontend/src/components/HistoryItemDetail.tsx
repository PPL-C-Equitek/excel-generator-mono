'use client'

import SessionConversationView from '@/components/SessionConversationView'
import type { SessionResume } from '@/services/sessions'
import type { ThinkingLogItem } from '@/services/thinkingLogs'
import type { HistoryItem } from '@/services/history'

interface HistoryItemDetailProps {
    readonly item: HistoryItem
    readonly editingHistoryId: string | null
    readonly renamingHistoryId: string | null
    readonly deletingHistoryId: string | null
    readonly renameValue: string
    readonly historyFileNameMaxLength: number
    readonly selectedSessionId: string | null
    readonly session: SessionResume | null
    readonly isLoadingSession: boolean
    readonly sessionError: string | null
    readonly isSessionNotFound: boolean
    readonly thinkingLogsByOutputId: Record<string, ThinkingLogItem>
    readonly isLoadingThinkingLogs: boolean
    readonly thinkingLogsError: string | null
    readonly setRenameValue: (nextValue: string) => void
    readonly startEditing: (item: HistoryItem) => void
    readonly stopEditing: () => void
    readonly handleRenameSubmit: (item: HistoryItem) => Promise<void>
    readonly requestDelete: (item: HistoryItem) => void
    readonly downloadCsv: (historyId: string, filename: string) => Promise<void>
    readonly downloadExcel: (historyId: string, filename: string) => Promise<void>
    readonly isDownloading: (historyId: string, format: 'csv' | 'xlsx') => boolean
    readonly getDisplayName: (customName: string, originalName: string) => string
    readonly getCsvFilename: (displayName: string) => string
    readonly getXlsxFilename: (displayName: string) => string
    readonly formatCreatedAt: (value: string) => string
}

export default function HistoryItemDetail({
    item,
    editingHistoryId,
    renamingHistoryId,
    deletingHistoryId,
    renameValue,
    historyFileNameMaxLength,
    selectedSessionId,
    session,
    isLoadingSession,
    sessionError,
    isSessionNotFound,
    thinkingLogsByOutputId,
    isLoadingThinkingLogs,
    thinkingLogsError,
    setRenameValue,
    startEditing,
    stopEditing,
    handleRenameSubmit,
    requestDelete,
    downloadCsv,
    downloadExcel,
    isDownloading,
    getDisplayName,
    getCsvFilename,
    getXlsxFilename,
    formatCreatedAt,
}: Readonly<HistoryItemDetailProps>) {
    const isEditing = editingHistoryId === item.id
    const isRenaming = renamingHistoryId === item.id
    const isDeleting = deletingHistoryId === item.id
    const isCsvDownloading = isDownloading(item.id, 'csv')
    const isExcelDownloading = isDownloading(item.id, 'xlsx')
    const historyName = getDisplayName(item.custom_name, item.original_name)

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                        Status
                    </p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">
                        {item.status_processing}
                    </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                        Created at
                    </p>
                    <p className="mt-2 text-sm font-semibold text-slate-900">
                        {formatCreatedAt(item.created_at)}
                    </p>
                </div>
            </div>

            {isEditing ? (
                <form
                    className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4"
                    onSubmit={(event) => {
                        event.preventDefault()
                        void handleRenameSubmit(item)
                    }}
                >
                    <div>
                        <label
                            htmlFor={`history-name-${item.id}`}
                            className="block text-sm font-semibold text-slate-900"
                        >
                            File Name
                        </label>
                        <input
                            id={`history-name-${item.id}`}
                            type="text"
                            value={renameValue}
                            onChange={(event) => {
                                setRenameValue(event.target.value)
                            }}
                            placeholder="Enter a file name"
                            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-red-300 focus:ring-2 focus:ring-red-100"
                            maxLength={historyFileNameMaxLength}
                            disabled={isRenaming}
                        />
                    </div>
                    <p className="text-xs text-slate-500">
                        Leave blank to use the uploaded file name. Up to {historyFileNameMaxLength} characters.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <button
                            type="submit"
                            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={isRenaming}
                        >
                            {isRenaming ? 'Saving...' : 'Save Name'}
                        </button>
                        <button
                            type="button"
                            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
                            onClick={stopEditing}
                            disabled={isRenaming}
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            ) : (
                <div className="flex flex-wrap gap-3">
                    <button
                        type="button"
                        className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => {
                            startEditing(item)
                        }}
                        disabled={isDeleting || isRenaming}
                    >
                        Edit Name
                    </button>
                    <button
                        type="button"
                        className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => {
                            requestDelete(item)
                        }}
                        disabled={isDeleting || isRenaming}
                    >
                        {isDeleting ? 'Deleting...' : 'Delete'}
                    </button>
                </div>
            )}

            <div className="flex flex-wrap gap-3">
                <button
                    type="button"
                    className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-red-700"
                    onClick={() => {
                        void downloadCsv(item.id, getCsvFilename(historyName))
                    }}
                    disabled={isCsvDownloading}
                >
                    {isCsvDownloading ? 'Downloading CSV...' : 'Download CSV'}
                </button>
                <button
                    type="button"
                    className="rounded-lg border border-red-700 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                    onClick={() => {
                        void downloadExcel(item.id, getXlsxFilename(historyName))
                    }}
                    disabled={isExcelDownloading}
                >
                    {isExcelDownloading ? 'Downloading Excel...' : 'Download Excel'}
                </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                {selectedSessionId ? (
                    <SessionConversationView
                        session={session}
                        isLoadingSession={isLoadingSession}
                        sessionError={sessionError}
                        isSessionNotFound={isSessionNotFound}
                        thinkingLogsByOutputId={thinkingLogsByOutputId}
                        isLoadingThinkingLogs={isLoadingThinkingLogs}
                        thinkingLogsError={thinkingLogsError}
                    />
                ) : (
                    <p className="text-sm text-slate-600">
                        Session context is not available for this history item, so per-session thinking logs cannot be loaded yet.
                    </p>
                )}
            </div>
        </div>
    )
}
