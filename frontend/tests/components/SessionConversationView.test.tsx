import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import SessionConversationView from '../../src/components/SessionConversationView'

function makeSession(overrides = {}) {
    return {
        id: 'session-1',
        title: 'Resume Session',
        created_at: '2026-04-10T10:00:00Z',
        updated_at: '2026-04-10T10:01:00Z',
        last_message_at: null,
        last_output_at: null,
        history: [
            {
                type: 'message',
                id: 'message-1',
                role: 'user',
                content: 'Tolong lanjutkan.',
                thinking_log: '',
                target_output_id: null,
                created_at: '2026-04-10T10:00:00Z',
            },
            {
                type: 'output',
                id: 'output-1',
                chat_id: null,
                parent_output_id: null,
                output_json: { summary: { total_rows: 1 } },
                thinking_log: 'Session fallback log',
                reasoning: { step1: 'Normalisasi' },
                created_at: '2026-04-10T10:01:00Z',
            },
        ],
        ...overrides,
    }
}

const thinkingLogsByOutputId = {
    'output-1': {
        id: 'output-1',
        session_id: 'session-1',
        chat_id: null,
        thinking_log: 'Server log',
        reasoning: ['step1'],
        status_processing: 'completed',
        created_at: '2026-04-10T10:01:00Z',
    },
}

describe('SessionConversationView', () => {
    it('renders loading, not found, and error states', () => {
        const { rerender } = render(
            <SessionConversationView
                session={null}
                isLoadingSession={true}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Loading session...')).toBeInTheDocument()

        rerender(
            <SessionConversationView
                session={null}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={true}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Session tidak ditemukan untuk history ini.')).toBeInTheDocument()

        rerender(
            <SessionConversationView
                session={null}
                isLoadingSession={false}
                sessionError={'Server error.'}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Server error.')).toBeInTheDocument()
    })

    it('returns nothing when the session is not yet available', () => {
        const { container } = render(
            <SessionConversationView
                session={null}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(container).toBeEmptyDOMElement()
    })

    it('renders the conversation and prefers server thinking logs over the session fallback', () => {
        render(
            <SessionConversationView
                session={makeSession()}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={thinkingLogsByOutputId}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Resume Session')).toBeInTheDocument()
        expect(screen.getByText('Tolong lanjutkan.')).toBeInTheDocument()
        expect(screen.getByText('Server log')).toBeInTheDocument()
        expect(screen.queryByText('Session fallback log')).not.toBeInTheDocument()

        const outputBlock = screen.getByText(/"total_rows": 1/).closest('article')
        expect(outputBlock).not.toBeNull()
        expect(within(outputBlock as HTMLElement).getByText('AI Output')).toBeInTheDocument()
    })

    it('shows loading and error states for output thinking logs when no content is available', () => {
        const session = makeSession({
            history: [
                {
                    type: 'output',
                    id: 'output-1',
                    chat_id: null,
                    parent_output_id: null,
                    output_json: { summary: { total_rows: 1 } },
                    thinking_log: '',
                    reasoning: {},
                    created_at: '2026-04-10T10:01:00Z',
                },
            ],
        })

        const { rerender } = render(
            <SessionConversationView
                session={session}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={true}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Memuat proses berpikir...')).toBeInTheDocument()

        rerender(
            <SessionConversationView
                session={session}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={'Failed to load thinking log.'}
            />
        )

        expect(screen.getByText('Gagal memuat proses')).toBeInTheDocument()
    })

    it('keeps raw timestamp text when history timestamp is invalid', () => {
        const session = makeSession({
            history: [
                {
                    type: 'message',
                    id: 'message-1',
                    role: 'user',
                    content: 'Ping',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: 'not-a-date',
                },
            ],
        })

        render(
            <SessionConversationView
                session={session}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('not-a-date')).toBeInTheDocument()
    })

    it('renders assistant bubble style and label for assistant messages', () => {
        const session = makeSession({
            history: [
                {
                    type: 'message',
                    id: 'message-assistant',
                    role: 'assistant',
                    content: 'Jawaban dari asisten.',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-04-10T10:00:00Z',
                },
            ],
        })

        render(
            <SessionConversationView
                session={session}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        const article = screen.getByText('Jawaban dari asisten.').closest('article')
        expect(article).not.toBeNull()
        expect(article).toHaveClass('justify-start')
        expect(screen.getByText('Assistant')).toBeInTheDocument()
    })
})