'use client'

import SessionConversationView from '@/components/SessionConversationView'
import type { SessionResume } from '@/services/sessions'
import type { ThinkingLogItem } from '@/services/thinkingLogs'

interface HistoryItemDetailProps {
    readonly selectedSessionId: string | null
    readonly session: SessionResume | null
    readonly isLoadingSession: boolean
    readonly sessionError: string | null
    readonly isSessionNotFound: boolean
    readonly thinkingLogsByOutputId: Record<string, ThinkingLogItem>
    readonly isLoadingThinkingLogs: boolean
    readonly thinkingLogsError: string | null
}

export default function HistoryItemDetail({
    selectedSessionId,
    session,
    isLoadingSession,
    sessionError,
    isSessionNotFound,
    thinkingLogsByOutputId,
    isLoadingThinkingLogs,
    thinkingLogsError,
}: Readonly<HistoryItemDetailProps>) {
    return (
        <div className="flex h-full min-h-0 flex-col">
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
                <p className="px-4 py-4 text-sm text-slate-600">
                    Session context is not available for this history item, so per-session thinking logs cannot be loaded yet.
                </p>
            )}
        </div>
    )
}
