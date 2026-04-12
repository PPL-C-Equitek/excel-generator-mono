'use client'

import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import type { HistoryItem } from '@/services/history'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const UTC_PLUS_SEVEN_OFFSET_HOURS = 7

function getDisplayName(customName: string, originalName: string): string {
    return customName.trim() || originalName
}

function getCsvFilename(displayName: string): string {
    return `${displayName.replace(/\.[^.]+$/, '')}.csv`
}

function getXlsxFilename(displayName: string): string {
    return `${displayName.replace(/\.[^.]+$/, '')}.xlsx`
}

function formatCreatedAt(value: string): string {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
        return value
    }

    const utcPlusSevenDate = new Date(
        date.getTime() + UTC_PLUS_SEVEN_OFFSET_HOURS * 60 * 60 * 1000
    )

    const day = String(utcPlusSevenDate.getUTCDate()).padStart(2, '0')
    const month = MONTH_LABELS[utcPlusSevenDate.getUTCMonth()]
    const year = utcPlusSevenDate.getUTCFullYear()
    const hours = String(utcPlusSevenDate.getUTCHours()).padStart(2, '0')
    const minutes = String(utcPlusSevenDate.getUTCMinutes()).padStart(2, '0')

    return `${day} ${month} ${year}, ${hours}:${minutes} UTC+7`
}

export default function HistoryPage() {
    const [editingHistoryId, setEditingHistoryId] = useState<string | null>(null)
    const [renameValue, setRenameValue] = useState('')
    const [historyToDelete, setHistoryToDelete] = useState<HistoryItem | null>(null)
    const {
        items,
        count,
        limit,
        offset,
        isLoading,
        renamingHistoryId,
        deletingHistoryId,
        isDownloading,
        loadError,
        downloadError,
        mutationError,
        reloadHistory,
        goToNextPage,
        goToPreviousPage,
        downloadCsv,
        downloadExcel,
        renameHistory,
        deleteHistory,
    } = useHistoryFiles()

    const hasNextPage = offset + limit < count
    const hasItems = items.length > 0
    const isDeleteDialogOpen = historyToDelete !== null
    const isDeletePending =
        historyToDelete !== null && deletingHistoryId === historyToDelete.id
    const actionError = mutationError ?? downloadError

    const startEditing = (item: HistoryItem) => {
        setEditingHistoryId(item.id)
        setRenameValue(getDisplayName(item.custom_name, item.original_name))
    }

    const stopEditing = () => {
        setEditingHistoryId(null)
        setRenameValue('')
    }

    const handleRenameSubmit = async (item: HistoryItem) => {
        const didRename = await renameHistory(item.id, renameValue.trim())
        if (didRename) {
            stopEditing()
        }
    }

    const handleDeleteConfirm = async () => {
        if (!historyToDelete) {
            return
        }

        const didDelete = await deleteHistory(historyToDelete.id)
        if (didDelete) {
            if (editingHistoryId === historyToDelete.id) {
                stopEditing()
            }
            setHistoryToDelete(null)
        }
    }

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="history" />
            <main className="ml-56 flex-1 px-8 py-12">
                <div className="mx-auto max-w-6xl space-y-8">
                    <section className="rounded-3xl border border-red-100 bg-white p-8 shadow-sm shadow-red-100/30">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div className="space-y-3">
                                <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-red-700">
                                    Download History
                                </span>
                                <div>
                                    <h1 className="text-2xl font-bold text-slate-900">History</h1>
                                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
                                        Your generated results are stored here for CSV or Excel
                                        download whenever you need them again.
                                    </p>
                                </div>
                            </div>
                            <div className="inline-flex rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                                Total records: <span className="ml-2 font-semibold text-slate-900">{count}</span>
                            </div>
                        </div>
                    </section>

                    {isLoading ? (
                        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
                            Loading history...
                        </div>
                    ) : null}

                    {!isLoading && loadError ? (
                        <div className="rounded-3xl border border-red-200 bg-white p-6 shadow-sm">
                            <p className="text-sm text-red-700">{loadError}</p>
                            <button
                                type="button"
                                className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300"
                                onClick={() => {
                                    void reloadHistory()
                                }}
                            >
                                Retry
                            </button>
                        </div>
                    ) : null}

                    {!isLoading && !loadError && !hasItems ? (
                        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
                            <h2 className="text-base font-semibold text-slate-900">No history yet</h2>
                            <p className="mt-2">
                                Generate a result first, then it will appear here for download.
                            </p>
                        </div>
                    ) : null}

                    {!isLoading && !loadError && hasItems ? (
                        <div className="space-y-4">
                            {actionError ? (
                                <div className="rounded-2xl border border-red-200 bg-white p-4 text-sm text-red-700 shadow-sm">
                                    {actionError}
                                </div>
                            ) : null}

                            <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
                                <p className="text-sm text-slate-500">
                                    Showing {offset + 1}-{Math.min(offset + items.length, count)} of {count}
                                </p>
                                <div className="flex items-center gap-3">
                                    <button
                                        type="button"
                                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                                        onClick={() => {
                                            void goToPreviousPage()
                                        }}
                                        disabled={offset === 0}
                                    >
                                        Previous
                                    </button>
                                    <button
                                        type="button"
                                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                                        onClick={() => {
                                            void goToNextPage()
                                        }}
                                        disabled={!hasNextPage}
                                    >
                                        Next
                                    </button>
                                </div>
                            </div>

                            {items.map((item) => (
                                <section
                                    key={item.id}
                                    className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-red-100/20"
                                >
                                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                        {(() => {
                                            const isEditing = editingHistoryId === item.id
                                            const isRenaming = renamingHistoryId === item.id
                                            const isDeleting = deletingHistoryId === item.id
                                            const isCsvDownloading = isDownloading(item.id, 'csv')
                                            const isExcelDownloading = isDownloading(item.id, 'xlsx')
                                            const historyName = getDisplayName(
                                                item.custom_name,
                                                item.original_name
                                            )

                                            return (
                                                <>
                                                    <div className="flex-1 space-y-3">
                                                        {isEditing ? (
                                                            <form
                                                                className="space-y-3"
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
                                                                        className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-red-300 focus:ring-2 focus:ring-red-100"
                                                                        maxLength={255}
                                                                        disabled={isRenaming}
                                                                    />
                                                                </div>
                                                                <p className="text-xs text-slate-500">
                                                                    Leave this blank to use the uploaded file name.
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
                                                            <h2 className="break-words text-lg font-semibold text-slate-900">
                                                                {historyName}
                                                            </h2>
                                                        )}
                                                        <p className="inline-flex w-fit rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-600">
                                                            Status: {item.status_processing}
                                                        </p>
                                                        <p className="text-sm text-slate-500">
                                                            Created at: {formatCreatedAt(item.created_at)}
                                                        </p>
                                                    </div>

                                                    <div className="flex flex-col gap-3 sm:items-end">
                                                        <div className="flex flex-wrap gap-3 sm:justify-end">
                                                            {!isEditing ? (
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
                                                            ) : null}
                                                            <button
                                                                type="button"
                                                                className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                                                                onClick={() => {
                                                                    setHistoryToDelete(item)
                                                                }}
                                                                disabled={isDeleting || isRenaming}
                                                            >
                                                                {isDeleting ? 'Deleting...' : 'Delete'}
                                                            </button>
                                                        </div>

                                                        <div className="flex flex-col gap-3 sm:flex-row">
                                                            <button
                                                                type="button"
                                                                className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-red-700"
                                                                onClick={() => {
                                                                    void downloadCsv(
                                                                        item.id,
                                                                        getCsvFilename(historyName)
                                                                    )
                                                                }}
                                                                disabled={isCsvDownloading}
                                                            >
                                                                {isCsvDownloading ? 'Downloading CSV...' : 'Download CSV'}
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="rounded-lg border border-red-700 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                                                                onClick={() => {
                                                                    void downloadExcel(
                                                                        item.id,
                                                                        getXlsxFilename(historyName)
                                                                    )
                                                                }}
                                                                disabled={isExcelDownloading}
                                                            >
                                                                {isExcelDownloading ? 'Downloading Excel...' : 'Download Excel'}
                                                            </button>
                                                        </div>
                                                    </div>
                                                </>
                                            )
                                        })()}
                                    </div>
                                </section>
                            ))}
                        </div>
                    ) : null}
                </div>
            </main>

            {isDeleteDialogOpen ? (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="delete-history-title"
                        className="w-full max-w-md rounded-3xl border border-red-100 bg-white p-6 shadow-2xl shadow-slate-900/15"
                    >
                        <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-red-700">
                            Delete History
                        </span>
                        <h2
                            id="delete-history-title"
                            className="mt-4 text-xl font-bold text-slate-900"
                        >
                            Delete this history item?
                        </h2>
                        <p className="mt-3 text-sm leading-relaxed text-slate-600">
                            This will remove{' '}
                            <span className="font-semibold text-slate-900">
                                {historyToDelete
                                    ? getDisplayName(
                                        historyToDelete.custom_name,
                                        historyToDelete.original_name
                                    )
                                    : ''}
                            </span>{' '}
                            from your history list and clear its cached download artifacts.
                        </p>
                        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                            <button
                                type="button"
                                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
                                onClick={() => {
                                    setHistoryToDelete(null)
                                }}
                                disabled={isDeletePending}
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                                onClick={() => {
                                    void handleDeleteConfirm()
                                }}
                                disabled={isDeletePending}
                            >
                                {isDeletePending ? 'Deleting...' : 'Delete History'}
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </div>
    )
}
