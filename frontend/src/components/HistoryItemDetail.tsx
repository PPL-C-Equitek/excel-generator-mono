'use client'

import SessionConversationView from '@/components/SessionConversationView'
import type { SessionResume } from '@/services/sessions'
import type { ThinkingLogItem } from '@/services/thinkingLogs'
import type { HistoryItem } from '@/services/history'
import { downloadSessionOutputCsvFile, downloadSessionOutputExcelFile } from '@/services/llm'
import { buildSessionOutputDownloadFilename } from '@/utils/sessionDownloadFilename'

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
    const isEditing = editingHistoryId === item.id
    const isRenaming = renamingHistoryId === item.id
    const isDeleting = deletingHistoryId === item.id
    const [isLatestCsvDownloading, setIsLatestCsvDownloading] = useState(false)
    const [isLatestExcelDownloading, setIsLatestExcelDownloading] = useState(false)
    const latestOutput = useMemo(() => {
        if (!session) {
            return null
        }

        const reversedHistory = [...session.history].reverse()
        return reversedHistory.find((entry) => entry.type === 'output') ?? null
    }, [session])

    const canDownloadLatestOutput = !!session?.id && !!latestOutput

    const handleDownloadLatestCsv = async () => {
        const sessionId = session!.id
        const output = latestOutput!

        setIsLatestCsvDownloading(true)
        try {
            await downloadSessionOutputCsvFile(
                sessionId,
                output.id,
                buildSessionOutputDownloadFilename(output, 'csv')
            )
        } finally {
            setIsLatestCsvDownloading(false)
        }
    }

    const handleDownloadLatestExcel = async () => {
        const sessionId = session!.id
        const output = latestOutput!

        setIsLatestExcelDownloading(true)
        try {
            await downloadSessionOutputExcelFile(
                sessionId,
                output.id,
                buildSessionOutputDownloadFilename(output, 'xlsx')
            )
        } finally {
            setIsLatestExcelDownloading(false)
        }
    }

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
