import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
    beforeEach(() => {
        mockUseSessionResume.mockReturnValue({
            session: null,
            isLoading: false,
            isNotFound: false,
            error: null,
        })
    })

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
        { label: 'not found message', payload: { isNotFound: false, error: 'Session not found.' } },
        { label: 'unauthorized', payload: { isNotFound: false, error: 'Unauthorized.' } },
        { label: '404 message', payload: { isNotFound: false, error: '404 not found' } },
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

    it('renders empty conversation fallback when session history is empty', () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession({ history: [] }),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-empty" />)

        expect(screen.getByText('No conversation history yet.')).toBeInTheDocument()
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

    it('does not submit when message is blank', async () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        const user = userEvent.setup()
        render(<SessionDetail sessionId="session-001" />)

        await user.click(screen.getByRole('button', { name: 'Send Message' }))

        expect(mockAppendSessionMessage).not.toHaveBeenCalled()
        expect(mockGetSessionResume).not.toHaveBeenCalled()
    })

    it('returns early in submit handler when form is submitted with empty draft', () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-001" />)

        const form = screen.getByRole('textbox', { name: 'Message Input' }).closest('form')
        expect(form).not.toBeNull()
        fireEvent.submit(form as HTMLFormElement)

        expect(mockAppendSessionMessage).not.toHaveBeenCalled()
        expect(mockGetSessionResume).not.toHaveBeenCalled()
    })

    it('restores draft and shows fallback error message when send fails with non-Error value', async () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })
        mockAppendSessionMessage.mockRejectedValue('network-failed')

        const user = userEvent.setup()
        render(<SessionDetail sessionId="session-001" />)

        const textbox = screen.getByRole('textbox', { name: 'Message Input' })
        await user.type(textbox, 'Coba lagi dong')
        await user.click(screen.getByRole('button', { name: 'Send Message' }))

        await waitFor(() => {
            expect(screen.getByText('Failed to send follow-up message.')).toBeInTheDocument()
            expect(screen.getByRole('textbox', { name: 'Message Input' })).toHaveValue('Coba lagi dong')
        })
    })

    it('shows exact thrown Error message when send fails with Error instance', async () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession(),
            isLoading: false,
            isNotFound: false,
            error: null,
        })
        mockAppendSessionMessage.mockRejectedValue(new Error('Server overloaded'))

        const user = userEvent.setup()
        render(<SessionDetail sessionId="session-001" />)

        await user.type(screen.getByRole('textbox', { name: 'Message Input' }), 'Retry this please')
        await user.click(screen.getByRole('button', { name: 'Send Message' }))

        await waitFor(() => {
            expect(screen.getByText('Server overloaded')).toBeInTheDocument()
        })
    })

    it('uses scrollIntoView when available to auto-scroll chat to bottom', () => {
        const scrollSpy = vi.fn()
        const original = Element.prototype.scrollIntoView
        Element.prototype.scrollIntoView = scrollSpy as Element['scrollIntoView']

        try {
            mockUseSessionResume.mockReturnValue({
                session: makeSession(),
                isLoading: false,
                isNotFound: false,
                error: null,
            })

            render(<SessionDetail sessionId="session-001" />)

            expect(scrollSpy).toHaveBeenCalled()
        } finally {
            Element.prototype.scrollIntoView = original
        }
    })

    it('falls back to container scroll flow when scrollIntoView is unavailable', () => {
        const originalScrollIntoView = Element.prototype.scrollIntoView
        const originalScrollHeightDescriptor = Object.getOwnPropertyDescriptor(
            HTMLElement.prototype,
            'scrollHeight'
        )
        Object.defineProperty(Element.prototype, 'scrollIntoView', {
            configurable: true,
            writable: true,
            value: undefined,
        })
        Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
            configurable: true,
            get: () => 240,
        })

        try {
            mockUseSessionResume.mockReturnValue({
                session: makeSession(),
                isLoading: false,
                isNotFound: false,
                error: null,
            })

            const { container } = render(<SessionDetail sessionId="session-001" />)
            const scrollContainer = container.querySelector('.overflow-y-auto') as HTMLDivElement

            expect(scrollContainer).not.toBeNull()
            expect(scrollContainer.scrollTop).toBe(240)
        } finally {
            Object.defineProperty(Element.prototype, 'scrollIntoView', {
                configurable: true,
                writable: true,
                value: originalScrollIntoView,
            })
            if (originalScrollHeightDescriptor) {
                Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeightDescriptor)
            }
        }
    })

    it('renders legacy fallback mode and supports legacy not-found/null branches', () => {
        const { rerender, container } = render(
            <SessionDetail
                session={{
                    id: 'legacy-1',
                    prompt: 'Legacy prompt',
                    score: 97,
                    evaluatedAt: 'invalid-evaluated-at',
                    output: 'legacy output text',
                }}
                isNotFound={false}
            />
        )

        expect(screen.getByText('legacy-1')).toBeInTheDocument()
        expect(screen.getByText('Legacy prompt')).toBeInTheDocument()
        expect(screen.getByText('97')).toBeInTheDocument()
        expect(screen.getByText('invalid-evaluated-at')).toBeInTheDocument()

        rerender(<SessionDetail session={null} isNotFound={true} />)
        expect(screen.getByText('Sesi Tidak Ditemukan')).toBeInTheDocument()

        rerender(<SessionDetail session={null} isNotFound={false} />)
        expect(container).toBeEmptyDOMElement()
    })

    it('returns null for by-id mode when loaded without session and without not-found flags', () => {
        mockUseSessionResume.mockReturnValue({
            session: null,
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        const { container } = render(<SessionDetail sessionId="session-unknown" />)
        expect(container).toBeEmptyDOMElement()
    })

    it('keeps invalid and null-like timestamps rendered without crashing', () => {
        mockUseSessionResume.mockReturnValue({
            session: makeSession({
                history: [
                    {
                        type: 'message',
                        id: 'message-invalid-time',
                        role: 'assistant',
                        content: 'Timestamp invalid',
                        thinking_log: '',
                        target_output_id: null,
                        created_at: 'not-a-date',
                    },
                    {
                        type: 'output',
                        id: 'output-null-time',
                        chat_id: null,
                        parent_output_id: null,
                        output_json: { value: 'ok' },
                        thinking_log: '',
                        reasoning: {},
                        created_at: null as unknown as string,
                    },
                ],
            }),
            isLoading: false,
            isNotFound: false,
            error: null,
        })

        render(<SessionDetail sessionId="session-invalid-time" />)

        expect(screen.getByText('not-a-date')).toBeInTheDocument()
        expect(screen.getByText('-')).toBeInTheDocument()
    })
})
