'use client'

import { useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import HistoryItemDetail from '@/components/HistoryItemDetail'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'
import { useSessionResume } from '@/hooks/useSessionResume'
import { useSessionThinkingLogs } from '@/hooks/useSessionThinkingLogs'

export default function HistoryPage() {
    const searchParams = useSearchParams()
    const selectedHistoryIdFromQuery = searchParams.get('historyId')
    const selectedSessionIdFromQuery = searchParams.get('sessionId')
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

    const noSelectionMessage = isLoading
        ? 'Loading history...'
        : (loadError || 'Choose a history item from the left panel to see details and actions.')

    return (
        <div className="flex h-screen overflow-hidden bg-gray-50">
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
            <main className="ml-56 flex h-screen min-h-0 flex-1 flex-col overflow-hidden bg-gray-50">
                <section className="flex min-h-0 flex-1 min-w-0 flex-col bg-gray-50">
                    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                        {actionError ? (
                            <div className="mx-4 mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:mx-6 lg:mx-8">
                                {actionError}
                            </div>
                        ) : null}

                        {selectedHistoryItem ? (
                            <div className="flex min-h-0 flex-1 flex-col">
                                <HistoryItemDetail
                                    selectedSessionId={selectedSessionId}
                                    session={session}
                                    isLoadingSession={isLoadingSession}
                                    sessionError={sessionError}
                                    isSessionNotFound={isSessionNotFound}
                                    thinkingLogsByOutputId={thinkingLogsByOutputId}
                                    isLoadingThinkingLogs={isLoadingThinkingLogs}
                                    thinkingLogsError={thinkingLogsError}
                                />
                            </div>
                        ) : (
                            <div className="m-4 rounded-2xl border border-slate-200 bg-slate-50 px-5 py-5 text-sm text-slate-600 sm:m-6 lg:m-8">
                                {noSelectionMessage}
                            </div>
                        )}
                    </div>
                </section>
            </main>
        </div>
    )
}
