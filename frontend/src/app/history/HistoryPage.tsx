'use client'

import { useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import type { HistoryItem } from '@/services/history'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const UTC_PLUS_SEVEN_OFFSET_HOURS = 7
const HISTORY_FILE_NAME_MAX_LENGTH = 120

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
    const searchParams = useSearchParams()
    const selectedHistoryIdFromQuery = searchParams.get('historyId')
    const [editingHistoryId, setEditingHistoryId] = useState<string | null>(null)
    const [renameValue, setRenameValue] = useState('')
    const [historyToDelete, setHistoryToDelete] = useState<HistoryItem | null>(null)
    const {
        items,
        isLoading,
        renamingHistoryId,
        deletingHistoryId,
        isDownloading,
        loadError,
        downloadError,
        mutationError,
        downloadCsv,
        downloadExcel,
        renameHistory,
        deleteHistory,
    } = useHistoryFiles({ loadAll: true, pageSize: 50 })

    const isDeleteDialogOpen = historyToDelete !== null
    const isDeletePending =
        historyToDelete !== null && deletingHistoryId === historyToDelete.id
    const actionError = mutationError ?? downloadError

    const selectedHistoryId = useMemo(() => {
        if (selectedHistoryIdFromQuery) {
            return selectedHistoryIdFromQuery
        }

        return items[0]?.id ?? null
    }, [items, selectedHistoryIdFromQuery])

    const selectedHistoryItem = useMemo(
        () => items.find((item) => item.id === selectedHistoryId) ?? null,
        [items, selectedHistoryId]
    )

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

    const handleDeleteConfirm = async (item: HistoryItem) => {
        const didDelete = await deleteHistory(item.id)
        if (didDelete) {
            stopEditing()
            setHistoryToDelete(null)
        }
    }

    const deleteDialogHistory = historyToDelete

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="history" selectedHistoryId={selectedHistoryId} />
            <main className="ml-56 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
                <div className="mx-auto h-[calc(100vh-4rem)] max-w-6xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-md shadow-slate-200/70">
                    <section className="h-full min-h-0 min-w-0 bg-white">
                        <div className="h-full overflow-y-auto px-5 py-5 sm:px-8 sm:py-6">
                            {actionError ? (
                                <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                    {actionError}
                                </div>
                            ) : null}

                            {!selectedHistoryItem ? (
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-5 text-sm text-slate-600">
                                    {isLoading
                                        ? 'Loading history...'
                                        : loadError
                                            ? loadError
                                            : 'Choose a history item from the left panel to see details and actions.'}
                                </div>
                            ) : (
                                (() => {
                                    const item = selectedHistoryItem
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
                                                            maxLength={HISTORY_FILE_NAME_MAX_LENGTH}
                                                            disabled={isRenaming}
                                                        />
                                                    </div>
                                                    <p className="text-xs text-slate-500">
                                                        Leave blank to use the uploaded file name. Up to {HISTORY_FILE_NAME_MAX_LENGTH} characters.
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
                                                            setHistoryToDelete(item)
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
                                        </div>
                                    )
                                })()
                            )}
                        </div>
                    </section>
                </div>
            </main>

            {isDeleteDialogOpen && deleteDialogHistory ? (
                <>
                    <div className="fixed inset-0 z-40 bg-slate-900/70" />
                    <dialog
                        open
                        aria-labelledby="delete-history-title"
                        className="fixed inset-0 z-50 m-auto w-full max-w-md rounded-3xl border border-red-100 bg-white p-6 shadow-2xl shadow-slate-900/15"
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
                                {getDisplayName(
                                    deleteDialogHistory.custom_name,
                                    deleteDialogHistory.original_name
                                )}
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
                                    void handleDeleteConfirm(deleteDialogHistory)
                                }}
                                disabled={isDeletePending}
                            >
                                {isDeletePending ? 'Deleting...' : 'Delete History'}
                            </button>
                        </div>
                    </dialog>
                </>
            ) : null}
        </div>
    )
}
