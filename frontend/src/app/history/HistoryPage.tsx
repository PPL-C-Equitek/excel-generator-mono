'use client'

import { useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import HistoryItemDetail from '@/components/HistoryItemDetail'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import { useSessionResume } from '@/hooks/useSessionResume'
import { useSessionThinkingLogs } from '@/hooks/useSessionThinkingLogs'
import type { HistoryItem } from '@/services/history'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const UTC_PLUS_SEVEN_OFFSET_HOURS = 7
const HISTORY_FILE_NAME_MAX_LENGTH = 120

function getDisplayName(customName: string, originalName: string): string {
    return customName.trim() || originalName
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
    const selectedSessionIdFromQuery = searchParams.get('sessionId')
    const [editingHistoryId, setEditingHistoryId] = useState<string | null>(null)
    const [renameValue, setRenameValue] = useState('')
    const [historyToDelete, setHistoryToDelete] = useState<HistoryItem | null>(null)
    const {
        items,
        isLoading,
        renamingHistoryId,
        deletingHistoryId,
        reloadHistory,
        loadError,
        downloadError,
        mutationError,
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
    const selectedSessionId = useMemo(() => {
        if (selectedSessionIdFromQuery) {
            return selectedSessionIdFromQuery
        }

        return selectedHistoryItem?.session_id ?? null
    }, [selectedHistoryItem?.session_id, selectedSessionIdFromQuery])
    const {
        session,
        isLoading: isLoadingSession,
        error: sessionError,
        isNotFound: isSessionNotFound,
    } = useSessionResume(selectedSessionId)
    const {
        thinkingLogsByOutputId,
        isLoading: isLoadingThinkingLogs,
        error: thinkingLogsError,
    } = useSessionThinkingLogs(selectedSessionId)

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
    const noSelectionMessage = isLoading
        ? 'Loading history...'
        : (loadError || 'Choose a history item from the left panel to see details and actions.')

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar
                activeMenu="history"
                selectedHistoryId={selectedHistoryId}
                historyListState={{
                    items,
                    isLoading,
                    loadError,
                    renamingHistoryId,
                    deletingHistoryId,
                    reloadHistory,
                    renameHistory,
                    deleteHistory,
                }}
            />
            <main className="ml-56 flex min-h-screen flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
                <div className="flex min-h-[calc(100vh-4rem)] w-full flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl">
                    <section className="flex min-h-0 flex-1 min-w-0 flex-col bg-white">
                        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 py-5 sm:px-8 sm:py-6">
                            {actionError ? (
                                <div role="alert" className="mb-5 rounded-lg border border-red-400 bg-red-50 px-4 py-3 text-sm text-red-700">
                                    {actionError}
                                </div>
                            ) : null}

                            {selectedHistoryItem ? (
                                <div className="flex min-h-0 flex-1 flex-col">
                                    <HistoryItemDetail
                                        item={selectedHistoryItem}
                                        editingHistoryId={editingHistoryId}
                                        renamingHistoryId={renamingHistoryId}
                                        deletingHistoryId={deletingHistoryId}
                                        renameValue={renameValue}
                                        historyFileNameMaxLength={HISTORY_FILE_NAME_MAX_LENGTH}
                                        selectedSessionId={selectedSessionId}
                                        session={session}
                                        isLoadingSession={isLoadingSession}
                                        sessionError={sessionError}
                                        isSessionNotFound={isSessionNotFound}
                                        thinkingLogsByOutputId={thinkingLogsByOutputId}
                                        isLoadingThinkingLogs={isLoadingThinkingLogs}
                                        thinkingLogsError={thinkingLogsError}
                                        setRenameValue={setRenameValue}
                                        startEditing={startEditing}
                                        stopEditing={stopEditing}
                                        handleRenameSubmit={handleRenameSubmit}
                                        requestDelete={setHistoryToDelete}
                                        formatCreatedAt={formatCreatedAt}
                                    />
                                </div>
                            ) : (
                                <div className="rounded-2xl border border-gray-200 bg-gray-50 px-5 py-5 text-sm text-gray-600">
                                    {noSelectionMessage}
                                </div>
                            )}
                        </div>
                    </section>
                </div>
            </main>

            {isDeleteDialogOpen && deleteDialogHistory ? (
                <>
                    <div className="fixed inset-0 z-40 bg-gray-900/70" />
                    <dialog
                        open
                        aria-labelledby="delete-history-title"
                        className="fixed inset-0 z-50 m-auto w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-xl"
                    >
                        <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-red-700">
                            Delete History
                        </span>
                        <h2
                            id="delete-history-title"
                            className="mt-4 text-xl font-bold text-gray-900"
                        >
                            Delete this history item?
                        </h2>
                        <p className="mt-3 text-sm leading-relaxed text-gray-600">
                            This will remove{' '}
                            <span className="font-semibold text-gray-900">
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
                                className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                                onClick={() => {
                                    setHistoryToDelete(null)
                                }}
                                disabled={isDeletePending}
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="rounded-xl bg-red-700 px-4 py-2 text-sm font-bold text-white shadow-md transition-all duration-150 hover:bg-red-800 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
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
