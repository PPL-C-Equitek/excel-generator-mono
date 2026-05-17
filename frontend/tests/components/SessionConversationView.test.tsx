import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SessionConversationView from '../../src/components/SessionConversationView'
import {
    downloadSessionOutputCsvFile,
    downloadSessionOutputExcelFile,
    generateJson,
} from '@/services/llm'

vi.mock('@/services/llm', () => ({
    generateJson: vi.fn(),
    downloadSessionOutputCsvFile: vi.fn(),
    downloadSessionOutputExcelFile: vi.fn(),
}))

const mockGenerateJson = vi.mocked(generateJson)
const mockDownloadSessionOutputCsvFile = vi.mocked(downloadSessionOutputCsvFile)
const mockDownloadSessionOutputExcelFile = vi.mocked(downloadSessionOutputExcelFile)

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
                export_output_json: {
                    document_info: { filename: 'invoice.pdf', source_type: 'PDF' },
                },
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
    afterEach(() => {
        vi.useRealTimers()
        vi.clearAllMocks()
    })

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

        expect(screen.getByText('Session Not Found')).toBeInTheDocument()

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
        expect(screen.getByText('Session Info')).toBeInTheDocument()
        expect(screen.getAllByText('Tolong lanjutkan.').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('Server log')).toBeInTheDocument()
        expect(screen.queryByText('Session fallback log')).not.toBeInTheDocument()
        expect(screen.getByText('Total Events')).toBeInTheDocument()
        expect(screen.getByText('User Prompts')).toBeInTheDocument()
        expect(screen.getByText('AI Outputs')).toBeInTheDocument()

        const outputBlock = screen.getByText('AI Output').closest('article')
        expect(outputBlock).not.toBeNull()
        expect(within(outputBlock as HTMLElement).getByText('Your file is ready.')).toBeInTheDocument()
        expect(within(outputBlock as HTMLElement).getByText('Download CSV')).toBeInTheDocument()
        expect(within(outputBlock as HTMLElement).getByText('Download Excel')).toBeInTheDocument()
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

        expect(screen.getByText('Loading thinking process...')).toBeInTheDocument()

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

        expect(screen.getByText('Failed to load process')).toBeInTheDocument()
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

    it('keeps invalid session metadata timestamps visible as raw text', () => {
        render(
            <SessionConversationView
                session={makeSession({
                    created_at: 'invalid-created-at',
                    updated_at: 'invalid-updated-at',
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('invalid-created-at')).toBeInTheDocument()
        expect(screen.getByText('invalid-updated-at')).toBeInTheDocument()
    })

    it('renders dash for missing session metadata timestamps', () => {
        render(
            <SessionConversationView
                session={makeSession({
                    created_at: null,
                    updated_at: null,
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(2)
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

    it('renders reasoning steps from reasoning object values when reasoning_steps is missing', () => {
        render(
            <SessionConversationView
                session={makeSession({
                    history: [
                        {
                            type: 'output',
                            id: 'output-reasoning-map',
                            chat_id: null,
                            parent_output_id: null,
                            output_json: { ok: true },
                            thinking_log: '',
                            reasoning: {
                                step_a: 'Valid step A',
                                step_b: 'Valid step B',
                                step_empty: '   ',
                                step_number: 123,
                            },
                            created_at: '2026-04-10T10:01:00Z',
                        },
                    ],
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={true}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('Reasoning steps')).toBeInTheDocument()
        expect(screen.getByText('Valid step A')).toBeInTheDocument()
        expect(screen.getByText('Valid step B')).toBeInTheDocument()
    })

    it('handles non-array non-object reasoning source without rendering reasoning steps', () => {
        render(
            <SessionConversationView
                session={makeSession({
                    history: [
                        {
                            type: 'output',
                            id: 'output-reasoning-scalar',
                            chat_id: null,
                            parent_output_id: null,
                            output_json: { ok: true },
                            thinking_log: '',
                            reasoning: 123 as unknown as Record<string, unknown>,
                            created_at: '2026-04-10T10:01:00Z',
                        },
                    ],
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={true}
                thinkingLogsError={null}
            />
        )

        expect(screen.queryByText('Reasoning steps')).not.toBeInTheDocument()
        expect(screen.getByText('Loading thinking process...')).toBeInTheDocument()
    })

    it('downloads output files from the output bubble actions', async () => {
        mockDownloadSessionOutputCsvFile.mockResolvedValue(undefined)
        mockDownloadSessionOutputExcelFile.mockResolvedValue(undefined)

        const user = userEvent.setup()
        render(
            <SessionConversationView
                session={makeSession()}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        await user.click(screen.getByRole('button', { name: 'Download CSV' }))
        await user.click(screen.getByRole('button', { name: 'Download Excel' }))

        await waitFor(() => {
            expect(mockDownloadSessionOutputCsvFile).toHaveBeenCalledWith(
                'session-1',
                'output-1',
                'invoice.csv'
            )
            expect(mockDownloadSessionOutputExcelFile).toHaveBeenCalledWith(
                'session-1',
                'output-1',
                'invoice.xlsx'
            )
        })
    })

    it('guards follow-up send when there is no latest output context', async () => {
        const user = userEvent.setup()
        render(
            <SessionConversationView
                session={makeSession({
                    history: [
                        {
                            type: 'message',
                            id: 'msg-only',
                            role: 'user',
                            content: 'Message only',
                            thinking_log: '',
                            target_output_id: null,
                            created_at: '2026-04-10T10:00:00Z',
                        },
                    ],
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'lanjut')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        expect(mockGenerateJson).not.toHaveBeenCalled()
        expect(
            screen.getByText('No output is available yet to continue this chat context.')
        ).toBeInTheDocument()
    })

    it('returns early when draft message is blank', () => {
        render(
            <SessionConversationView
                session={makeSession()}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        const sendButton = screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement
        sendButton.removeAttribute('disabled')

        fireEvent.click(sendButton)

        expect(mockGenerateJson).not.toHaveBeenCalled()
    })

    it('syncs to incoming server history updates for the active session', () => {
        const initialSession = makeSession({
            history: [
                {
                    type: 'message',
                    id: 'msg-1',
                    role: 'user',
                    content: 'awal',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-04-10T10:00:00Z',
                },
            ],
        })
        const updatedSession = {
            ...initialSession,
            history: [
                ...initialSession.history,
                {
                    type: 'message',
                    id: 'msg-2',
                    role: 'assistant',
                    content: 'balasan baru',
                    thinking_log: '',
                    target_output_id: null,
                    created_at: '2026-04-10T10:01:00Z',
                },
            ],
        }

        const { rerender } = render(
            <SessionConversationView
                session={initialSession}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        rerender(
            <SessionConversationView
                session={updatedSession}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={{}}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('balasan baru')).toBeInTheDocument()
    })

    it('restores draft and shows fallback error when follow-up generation fails with non-Error', async () => {
        mockGenerateJson.mockRejectedValueOnce('failed')

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'fail case')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(screen.getByText('Failed to send follow-up message.')).toBeInTheDocument()
            expect(screen.getByRole('textbox', { name: 'Follow-up message' })).toHaveValue('fail case')
            expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled()
        })
    })

    it('shows explicit error message when follow-up generation throws Error', async () => {
        mockGenerateJson.mockRejectedValueOnce(new Error('backend down'))

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'error case')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(screen.getByText('backend down')).toBeInTheDocument()
        })
    })

    it('keeps optimistic local items when same-session props re-render without them', async () => {
        let resolveRequest: ((value: unknown) => void) | null = null
        mockGenerateJson.mockImplementationOnce(
            () =>
                new Promise((resolve) => {
                    resolveRequest = resolve
                })
        )

        const user = userEvent.setup()
        const session = makeSession()
        const { rerender } = render(
            <SessionConversationView
                session={session}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={thinkingLogsByOutputId}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'optimistic msg')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(screen.getByText('optimistic msg')).toBeInTheDocument()
            expect(screen.getByText('AI Thinking')).toBeInTheDocument()
        })

        rerender(
            <SessionConversationView
                session={{ ...session, history: [...session.history] }}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={thinkingLogsByOutputId}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        expect(screen.getByText('optimistic msg')).toBeInTheDocument()

        resolveRequest?.({
            output_json: { summary: { status: 'ok' } },
            session_id: 'session-1',
            chat_id: 'chat-final',
            output_id: 'output-final',
            reasoning: {
                reasoning_steps: ['step 1'],
                final_answer: 'ok',
                thinking_log: 'done',
            },
        })

        await waitFor(() => {
            expect(screen.getByText('done')).toBeInTheDocument()
        })
    })

    it('auto-scrolls using scrollIntoView when available', () => {
        const original = Element.prototype.scrollIntoView
        const spy = vi.fn()
        Element.prototype.scrollIntoView = spy as Element['scrollIntoView']

        try {
            render(
                <SessionConversationView
                    session={makeSession()}
                    isLoadingSession={false}
                    sessionError={null}
                    isSessionNotFound={false}
                    thinkingLogsByOutputId={{}}
                    isLoadingThinkingLogs={false}
                    thinkingLogsError={null}
                />
            )

            expect(spy).toHaveBeenCalled()
        } finally {
            Element.prototype.scrollIntoView = original
        }
    })

    it('normalizes non-object output_json into a result object', async () => {
        mockGenerateJson.mockResolvedValueOnce({
            output_json: 'plain-text-result',
            session_id: 'session-1',
            chat_id: 'chat-scalar',
            output_id: 'output-scalar',
            reasoning: {
                final_answer: 'Done',
                reasoning_steps: ['scalar-step'],
                thinking_log: 'scalar-thinking',
            },
        })

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'scalar out')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(mockGenerateJson).toHaveBeenCalled()
            expect(screen.getByText('scalar-thinking')).toBeInTheDocument()
        })
    })

    it('uses safe defaults when optional follow-up response fields are missing', async () => {
        mockGenerateJson.mockResolvedValueOnce({
            output_json: { ok: true },
            session_id: 'session-1',
        })

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'fallback path')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(mockGenerateJson).toHaveBeenCalledTimes(1)
        })
        expect(screen.getByText('AI Thinking')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled()
    })

    it('returns early when send is triggered again while request is still sending', async () => {
        let resolveGenerate: ((value: unknown) => void) | null = null
        mockGenerateJson.mockImplementationOnce(
            () =>
                new Promise((resolve) => {
                    resolveGenerate = resolve
                })
        )

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'double-send')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        const sendingButton = screen.getByRole('button', { name: 'Sending...' }) as HTMLButtonElement
        sendingButton.disabled = false
        fireEvent.click(sendingButton)

        expect(mockGenerateJson).toHaveBeenCalledTimes(1)

        resolveGenerate?.({
            output_json: { done: true },
            session_id: 'session-1',
            chat_id: 'chat-done',
            output_id: 'output-done',
            reasoning: {
                reasoning_steps: ['step'],
                final_answer: 'done',
                thinking_log: 'done',
            },
        })

        await waitFor(() => {
            expect(screen.getByText('done')).toBeInTheDocument()
        })
    })

    it('renders follow-up composer and sends message via LLM generate with current session context', async () => {
        mockGenerateJson.mockResolvedValueOnce({
            output_json: { summary: { status: 'done' } },
            session_id: 'session-1',
            chat_id: 'chat-2',
            output_id: 'output-2',
            reasoning: {
                final_answer: 'Done',
                reasoning_steps: ['step-1'],
                thinking_log: 'Thinking follow up',
            },
        })

        const user = userEvent.setup()
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

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'Lanjutkan analisisnya')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(mockGenerateJson).toHaveBeenCalledWith(
                {
                    user_prompt: 'Lanjutkan analisisnya',
                },
                undefined,
                undefined,
                {
                    sessionId: 'session-1',
                    targetOutputId: 'output-1',
                }
            )
            expect(screen.getByText('Lanjutkan analisisnya')).toBeInTheDocument()
            expect(screen.getByText('Thinking follow up')).toBeInTheDocument()
        })
    })

    it('uses previous_output fallback when latest output id is temporary', async () => {
        mockGenerateJson.mockResolvedValueOnce({
            output_json: { summary: { status: 'done' } },
            session_id: 'session-1',
            chat_id: 'chat-2',
            output_id: 'output-2',
            reasoning: {
                final_answer: 'Done',
                reasoning_steps: ['step-1'],
                thinking_log: 'Thinking follow up',
            },
        })

        const user = userEvent.setup()
        render(
            <SessionConversationView
                session={makeSession({
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
                            id: 'temp-output-1',
                            chat_id: null,
                            parent_output_id: null,
                            output_json: { summary: { total_rows: 1 } },
                            thinking_log: 'Session fallback log',
                            reasoning: { step1: 'Normalisasi' },
                            created_at: '2026-04-10T10:01:00Z',
                        },
                    ],
                })}
                isLoadingSession={false}
                sessionError={null}
                isSessionNotFound={false}
                thinkingLogsByOutputId={thinkingLogsByOutputId}
                isLoadingThinkingLogs={false}
                thinkingLogsError={null}
            />
        )

        await user.type(screen.getByRole('textbox', { name: 'Follow-up message' }), 'Lanjutkan analisisnya')
        await user.click(screen.getByRole('button', { name: 'Send' }))

        await waitFor(() => {
            expect(mockGenerateJson).toHaveBeenCalledWith(
                {
                    previous_output: { summary: { total_rows: 1 } },
                    user_prompt: 'Lanjutkan analisisnya',
                },
                undefined,
                undefined,
                {
                    sessionId: 'session-1',
                    targetOutputId: undefined,
                }
            )
        })
    })
})
