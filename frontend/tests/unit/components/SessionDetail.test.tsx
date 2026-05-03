import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SessionDetail from '@/components/SessionDetail'
import { useSessionResume } from '@/hooks/useSessionResume'
import { appendSessionMessage, getSessionResume, type SessionResume } from '@/services/sessions'

vi.mock('@/hooks/useSessionResume', () => ({
    useSessionResume: vi.fn(),
}))

vi.mock('@/services/sessions', async () => {
    const actual = await vi.importActual<typeof import('@/services/sessions')>('@/services/sessions')
    return {
        ...actual,
        appendSessionMessage: vi.fn(),
        getSessionResume: vi.fn(),
    }
})

const mockUseSessionResume = vi.mocked(useSessionResume)
const mockAppendSessionMessage = vi.mocked(appendSessionMessage)
const mockGetSessionResume = vi.mocked(getSessionResume)

function makeSession(overrides: Partial<SessionResume> = {}): SessionResume {
    return {
        id: 'session-001',
        title: 'Analisis Data April',
        created_at: '2026-05-03T08:00:00.000Z',
        updated_at: '2026-05-03T08:10:00.000Z',
        last_message_at: '2026-05-03T08:09:00.000Z',
        last_output_at: '2026-05-03T08:10:00.000Z',
        history: [
            {
                type: 'message',
                id: 'message-1',
                role: 'user',
                content: 'Tolong rangkum data ini.',
                thinking_log: '',
                target_output_id: null,
                created_at: '2026-05-03T08:00:00.000Z',
            },
            {
                type: 'message',
                id: 'message-2',
                role: 'assistant',
                content: 'Baik, saya rangkum dulu poin utamanya.',
                thinking_log: '',
                target_output_id: null,
                created_at: '2026-05-03T08:01:00.000Z',
            },
            {
                type: 'output',
                id: 'output-1',
                chat_id: 'chat-001',
                parent_output_id: null,
                output_json: { result: { total_rows: 123 } },
                thinking_log: 'Membaca tabel dan mengecek kolom.',
                reasoning: { step1: 'Normalisasi data mentah' },
                created_at: '2026-05-03T08:02:00.000Z',
            },
        ],
        ...overrides,
    }
}

describe('SessionDetail Chat Thread', () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it('renders loading state while waiting for /sessions/{id}/resume', () => {
        mockUseSessionResume.mockReturnValue({
            session: null,
            isLoading: true,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-001" />)

        expect(screen.getByText('Loading session...')).toBeInTheDocument()
    })

    it.each([
        { label: '404', payload: { isNotFound: true, error: null } },
        { label: '403', payload: { isNotFound: false, error: 'Forbidden.' } },
    ])('renders "Sesi Tidak Ditemukan" for $label session error state', ({ payload }) => {
        mockUseSessionResume.mockReturnValue({
            session: null,
            isLoading: false,
            isNotFound: payload.isNotFound,
            error: payload.error,
        })

        render(<SessionDetail sessionId="session-404" />)

        expect(screen.getByText('Sesi Tidak Ditemukan')).toBeInTheDocument()
    })

    it('renders full chat history thread with user and AI messages', () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-001" />)

        expect(screen.getAllByText('Tolong rangkum data ini.').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('Baik, saya rangkum dulu poin utamanya.')).toBeInTheDocument()
        expect(screen.getByText('AI Output')).toBeInTheDocument()
    })

    it('renders chat input form at the bottom area of the session view', () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-001" />)

        expect(screen.getByRole('textbox', { name: 'Message Input' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Send Message' })).toBeInTheDocument()
    })

    it('keeps AI output wrapped for long code blocks and huge rows', () => {
        const longChunk = 'X'.repeat(800)
        mockUseSessionResume.mockReturnValue({
            session: makeSession({
                history: [
                    {
                        type: 'output',
                        id: 'output-edge',
                        chat_id: 'chat-edge',
                        parent_output_id: null,
                        output_json: {
                            markdown: `|header|value|\n|---|---|\n|${longChunk}|${longChunk}|`,
                            code: `const payload="${longChunk}"`,
                        },
                        thinking_log: '',
                        reasoning: {},
                        created_at: '2026-05-03T08:02:00.000Z',
                    },
                ],
            }),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-edge" />)

        const outputRegion = screen.getByLabelText('AI Output Content')
        const horizontalScrollContainer = outputRegion.querySelector('.overflow-x-auto')
        const codeNode = outputRegion.querySelector('code')

        expect(horizontalScrollContainer).not.toBeNull()
        expect(codeNode).not.toBeNull()
        expect(codeNode).toHaveClass('break-words')
    })

    it('sends follow-up message to current sessionId and appends refreshed history', async () => {
        const initialSession = makeSession()
        const refreshedSession = makeSession({
            history: [
                ...initialSession.history,
                {
                    type: 'message',
                    id: 'message-3',
                    role: 'user',
                    content: 'Lanjutkan ke unit Radiologi ya.',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-05-03T08:11:00.000Z',
                },
            ],
        })

        mockUseSessionResume.mockReturnValue({
            session: initialSession,
            isLoading: false,
            isNotFound: false,
            error: null,
        })
        mockAppendSessionMessage.mockResolvedValue({
            ok: true,
            session_id: 'session-001',
            chat_id: 'chat-001',
        })
        mockGetSessionResume.mockResolvedValue(refreshedSession)

        const user = userEvent.setup()
        render(<SessionDetail sessionId="session-001" />)

        await user.type(screen.getByRole('textbox', { name: 'Message Input' }), 'Lanjutkan ke unit Radiologi ya.')
        await user.click(screen.getByRole('button', { name: 'Send Message' }))

        await waitFor(() => {
            expect(mockAppendSessionMessage).toHaveBeenCalledWith(
                'session-001',
                'Lanjutkan ke unit Radiologi ya.'
            )
            expect(mockGetSessionResume).toHaveBeenCalledWith('session-001')
            expect(screen.getByText('Lanjutkan ke unit Radiologi ya.')).toBeInTheDocument()
        })
    })
})
