import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import HistoryItemDetail from '@/components/HistoryItemDetail'
import type { HistoryItem } from '@/services/history'
import type { SessionResume } from '@/services/sessions'
import { downloadSessionOutputCsvFile, downloadSessionOutputExcelFile } from '@/services/llm'

vi.mock('@/components/SessionConversationView', () => ({
    default: () => <div data-testid="session-conversation-view">SessionConversationView</div>,
}))

vi.mock('@/services/llm', () => ({
    downloadSessionOutputCsvFile: vi.fn(),
    downloadSessionOutputExcelFile: vi.fn(),
}))

const mockDownloadSessionOutputCsvFile = vi.mocked(downloadSessionOutputCsvFile)
const mockDownloadSessionOutputExcelFile = vi.mocked(downloadSessionOutputExcelFile)

const baseItem: HistoryItem = {
    id: 'history-1',
    original_name: 'report.pdf',
    custom_name: '',
    session_id: null,
    status_processing: 'completed',
    created_at: '2026-05-03T10:00:00.000Z',
}

function makeSession(history: SessionResume['history']): SessionResume {
    return {
        id: 'session-1',
        title: 'Session One',
        created_at: '2026-05-03T10:00:00.000Z',
        updated_at: '2026-05-03T10:10:00.000Z',
        last_message_at: null,
        last_output_at: null,
        history,
    }
}

function renderComponent(overrides: Partial<ComponentProps<typeof HistoryItemDetail>> = {}) {
    return render(
        <HistoryItemDetail
            item={baseItem}
            editingHistoryId={null}
            renamingHistoryId={null}
            deletingHistoryId={null}
            renameValue=""
            historyFileNameMaxLength={100}
            selectedSessionId={null}
            session={null}
            isLoadingSession={false}
            sessionError={null}
            isSessionNotFound={false}
            thinkingLogsByOutputId={{}}
            isLoadingThinkingLogs={false}
            thinkingLogsError={null}
            setRenameValue={vi.fn()}
            startEditing={vi.fn()}
            stopEditing={vi.fn()}
            handleRenameSubmit={vi.fn()}
            requestDelete={vi.fn()}
            formatCreatedAt={(value: string) => value}
            {...overrides}
        />
    )
}

describe('HistoryItemDetail', () => {
    it('shows session-context fallback message when selectedSessionId is unavailable', () => {
        renderComponent()
        expect(
            screen.getByText(
                'Session context is not available for this history item, so per-session thinking logs cannot be loaded yet.'
            )
        ).toBeInTheDocument()
    })

    it('disables latest export buttons when session exists but has no output item', () => {
        renderComponent({
            selectedSessionId: 'session-1',
            session: makeSession([
                {
                    type: 'message',
                    id: 'message-1',
                    role: 'user',
                    content: 'hello',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-05-03T10:00:00.000Z',
                },
            ]),
        })

        const latestCsvButton = screen.getByRole('button', { name: 'Download latest as CSV' })
        const latestExcelButton = screen.getByRole('button', { name: 'Download latest as Excel' })

        expect(latestCsvButton).toBeDisabled()
        expect(latestExcelButton).toBeDisabled()
    })

    it('downloads latest output csv and excel when output exists in session history', async () => {
        mockDownloadSessionOutputCsvFile.mockResolvedValue(undefined)
        mockDownloadSessionOutputExcelFile.mockResolvedValue(undefined)

        renderComponent({
            selectedSessionId: 'session-1',
            session: makeSession([
                {
                    type: 'message',
                    id: 'message-1',
                    role: 'user',
                    content: 'hello',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-05-03T10:00:00.000Z',
                },
                {
                    type: 'output',
                    id: 'output-2',
                    chat_id: null,
                    parent_output_id: null,
                    output_json: { ok: true },
                    thinking_log: '',
                    reasoning: {},
                    created_at: '2026-05-03T10:01:00.000Z',
                },
            ]),
        })

        const latestCsvButton = screen.getByRole('button', { name: 'Download latest as CSV' })
        const latestExcelButton = screen.getByRole('button', { name: 'Download latest as Excel' })
        const user = userEvent.setup()

        await user.click(latestCsvButton)
        await user.click(latestExcelButton)

        await waitFor(() => {
            expect(mockDownloadSessionOutputCsvFile).toHaveBeenCalledWith(
                'session-1',
                'output-2',
                'session-session-1-latest-output.csv'
            )
            expect(mockDownloadSessionOutputExcelFile).toHaveBeenCalledWith(
                'session-1',
                'output-2',
                'session-session-1-latest-output.xlsx'
            )
        })
    })
})
