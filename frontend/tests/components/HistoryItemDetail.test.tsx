import { render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import HistoryItemDetail from '@/components/HistoryItemDetail'
import type { SessionResume } from '@/services/sessions'

vi.mock('@/components/SessionConversationView', () => ({
    default: () => <div data-testid="session-conversation-view">SessionConversationView</div>,
}))

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
            selectedSessionId={null}
            session={null}
            isLoadingSession={false}
            sessionError={null}
            isSessionNotFound={false}
            thinkingLogsByOutputId={{}}
            isLoadingThinkingLogs={false}
            thinkingLogsError={null}
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

    it('renders only the session conversation when session context exists', () => {
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
                    export_output_json: {
                        document_info: { filename: 'report.pdf', source_type: 'PDF' },
                    },
                    thinking_log: '',
                    reasoning: {},
                    created_at: '2026-05-03T10:01:00.000Z',
                },
            ]),
        })
        expect(screen.getByTestId('session-conversation-view')).toBeInTheDocument()
        expect(
            screen.queryByText(
                'Session context is not available for this history item, so per-session thinking logs cannot be loaded yet.'
            )
        ).not.toBeInTheDocument()
    })
})
