'use client'

import { type FormEventHandler, useEffect, useMemo, useRef, useState } from 'react'
import ThinkingPanel, { THINKING_PANEL_STATUS } from '@/components/ThinkingPanel'
import { useSessionResume } from '@/hooks/useSessionResume'
import {
    appendSessionMessage,
    getSessionResume,
    type SessionResume,
    type SessionResumeHistoryItem,
} from '@/services/sessions'

export interface Session {
    id: string
    prompt: string
    score: number
    evaluatedAt: string
    output: string
}

interface SessionDetailStateProps {
    session: Session | null
    isNotFound: boolean
}

interface SessionDetailByIdProps {
    sessionId: string | null
}

export type SessionDetailProps = SessionDetailStateProps | SessionDetailByIdProps

function isNotFoundErrorMessage(error: string | null): boolean {
    if (!error) {
        return false
    }

    const normalized = error.trim().toLowerCase()
    return (
        normalized.includes('not found') ||
        normalized.includes('404') ||
        normalized.includes('forbidden') ||
        normalized.includes('unauthorized')
    )
}

function formatSessionDate(value: string | null): string {
    if (!value) {
        return '-'
    }

    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return value
    }

    return parsed.toLocaleString('id-ID', {
        dateStyle: 'medium',
        timeStyle: 'short',
    })
}

function SessionNotFound() {
    return (
        <output
            aria-live="polite"
            className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-800"
        >
            <h1 className="text-lg font-semibold">Sesi Tidak Ditemukan</h1>
        </output>
    )
}

function SessionMessageBubble({
    item,
}: Readonly<{
    item: Extract<SessionResumeHistoryItem, { type: 'message' }>
}>) {
    const isUser = item.role === 'user'

    return (
        <article className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`max-w-3xl rounded-2xl px-4 py-3 shadow-sm ${
                    isUser
                        ? 'bg-blue-600 text-white'
                        : 'border border-slate-200 bg-white text-slate-800'
                }`}
            >
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] opacity-75">
                    {isUser ? 'User Prompt' : 'Assistant'}
                </p>
                <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm leading-6">
                    {item.content}
                </p>
                <p className="mt-2 text-[11px] opacity-70">{formatSessionDate(item.created_at)}</p>
            </div>
        </article>
    )
}

function SessionOutputBubble({
    item,
}: Readonly<{
    item: Extract<SessionResumeHistoryItem, { type: 'output' }>
}>) {
    const outputText = JSON.stringify(item.output_json, null, 2)
    const thinkingLog = item.thinking_log.trim()

    return (
        <article className="flex justify-start">
            <div className="max-w-4xl rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                    AI Output
                </p>

                <ThinkingPanel
                    status={
                        thinkingLog ? THINKING_PANEL_STATUS.success : THINKING_PANEL_STATUS.loading
                    }
                    content={thinkingLog}
                    animated={!thinkingLog}
                />

                <div
                    aria-label="AI Output Content"
                    className="mt-3 break-words overflow-hidden rounded-xl border border-slate-200 bg-slate-950"
                >
                    <div className="max-w-full overflow-x-auto">
                        <pre className="min-w-max p-4 text-xs leading-6 text-slate-100">
                            <code className="break-words [overflow-wrap:anywhere]">{outputText}</code>
                        </pre>
                    </div>
                </div>
                <p className="mt-2 text-[11px] text-slate-500">{formatSessionDate(item.created_at)}</p>
            </div>
        </article>
    )
}

function SessionHistoryList({ history }: Readonly<{ history: SessionResumeHistoryItem[] }>) {
    if (history.length === 0) {
        return (
            <section className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                No conversation history yet.
            </section>
        )
    }

    return (
        <section className="space-y-4" aria-label="Session Conversation">
            {history.map((item) =>
                item.type === 'message' ? (
                    <SessionMessageBubble key={`${item.type}-${item.id}`} item={item} />
                ) : (
                    <SessionOutputBubble key={`${item.type}-${item.id}`} item={item} />
                )
            )}
        </section>
    )
}

function isNonEmptyUserMessage(
    item: SessionResumeHistoryItem
): item is Extract<SessionResumeHistoryItem, { type: 'message' }> {
    return item.type === 'message' && item.role === 'user' && item.content.trim().length > 0
}

function SessionDetailByIdContent({ session }: Readonly<{ session: SessionResume }>) {
    const [draft, setDraft] = useState('')
    const [sendError, setSendError] = useState<string | null>(null)
    const [isSending, setIsSending] = useState(false)
    const [localSession, setLocalSession] = useState<SessionResume>(session)
    const scrollContainerRef = useRef<HTMLDivElement | null>(null)
    const bottomAnchorRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        setLocalSession(session)
    }, [session])

    useEffect(() => {
        if (bottomAnchorRef.current && typeof bottomAnchorRef.current.scrollIntoView === 'function') {
            bottomAnchorRef.current.scrollIntoView({ block: 'end', behavior: 'smooth' })
            return
        }

        /* v8 ignore if -- @preserve jsdom path is flaky; covered in real browser when scrollIntoView is absent */
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
        }
    }, [localSession.history.length])

    const canSend = draft.trim().length > 0 && !isSending

    const title = useMemo(() => {
        const firstPrompt = localSession.history.find(isNonEmptyUserMessage)
        return firstPrompt?.content ?? localSession.title
    }, [localSession.history, localSession.title])

    const handleSendMessage: FormEventHandler<HTMLFormElement> = async (event) => {
        event.preventDefault()
        const trimmedMessage = draft.trim()
        if (!trimmedMessage || isSending) {
            return
        }

        const optimisticMessage: SessionResumeHistoryItem = {
            type: 'message',
            id: `temp-${Date.now()}`,
            role: 'user',
            content: trimmedMessage,
            thinking_log: '',
            target_output_id: null,
            created_at: new Date().toISOString(),
        }

        setDraft('')
        setSendError(null)
        setIsSending(true)
        setLocalSession((prev) => ({
            ...prev,
            history: [...prev.history, optimisticMessage],
        }))

        try {
            await appendSessionMessage(localSession.id, trimmedMessage)
            const refreshedSession = await getSessionResume(localSession.id)
            setLocalSession(refreshedSession)
        } catch (error: unknown) {
            const errorMessage =
                error instanceof Error ? error.message : 'Failed to send follow-up message.'
            setSendError(errorMessage)
            setLocalSession((prev) => ({
                ...prev,
                history: prev.history.filter((item) => item.id !== optimisticMessage.id),
            }))
            setDraft(trimmedMessage)
        } finally {
            setIsSending(false)
        }
    }

    return (
        <section className="flex h-full min-h-[70vh] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <header className="border-b border-slate-200 px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                    Session Thread
                </p>
                <h1 className="mt-1 line-clamp-2 text-lg font-bold text-slate-900">{title}</h1>
                <p className="mt-1 text-xs text-slate-500">{localSession.id}</p>
            </header>

            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
                <SessionHistoryList history={localSession.history} />
                <div ref={bottomAnchorRef} />
            </div>

            <form
                onSubmit={handleSendMessage}
                className="sticky bottom-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-6"
            >
                <label htmlFor="session-chat-input" className="sr-only">
                    Message Input
                </label>
                <div className="flex items-end gap-3">
                    <textarea
                        id="session-chat-input"
                        aria-label="Message Input"
                        value={draft}
                        onChange={(event) => {
                            setDraft(event.target.value)
                        }}
                        placeholder="Ketik follow-up kamu di sini..."
                        rows={2}
                        className="min-h-[44px] w-full resize-y rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                        disabled={isSending}
                    />
                    <button
                        type="submit"
                        aria-label="Send Message"
                        className="h-11 shrink-0 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={!canSend}
                    >
                        {isSending ? 'Sending...' : 'Send'}
                    </button>
                </div>
                {sendError ? <p className="mt-2 text-xs text-red-700">{sendError}</p> : null}
            </form>
        </section>
    )
}

function SessionDetailLegacyContent({
    session,
    isNotFound,
}: Readonly<SessionDetailStateProps>) {
    if (isNotFound) {
        return <SessionNotFound />
    }

    if (!session) {
        return null
    }

    return (
        <article className="space-y-4" aria-labelledby="session-detail-title">
            <header>
                <h1 id="session-detail-title">{session.id}</h1>
            </header>

            <dl>
                <dt>Prompt</dt>
                <dd>{session.prompt}</dd>

                <dt>Score</dt>
                <dd>{session.score}</dd>

                <dt>Evaluated At</dt>
                <dd>{session.evaluatedAt}</dd>
            </dl>

            <section aria-label="Session Output">
                <div className="break-words overflow-hidden rounded-xl border border-slate-200 bg-slate-950">
                    <div className="max-w-full overflow-x-auto">
                        <pre className="max-h-96 p-4 text-xs leading-6 text-slate-100">
                            <p className="break-words [overflow-wrap:anywhere] whitespace-pre-wrap">
                                {session.output}
                            </p>
                        </pre>
                    </div>
                </div>
            </section>
        </article>
    )
}

export default function SessionDetail(props: Readonly<SessionDetailProps>) {
    const sessionId = 'sessionId' in props ? props.sessionId : null
    const { session, isLoading, isNotFound, error } = useSessionResume(
        sessionId
    )

    if ('session' in props && 'isNotFound' in props) {
        return <SessionDetailLegacyContent session={props.session} isNotFound={props.isNotFound} />
    }

    if (isLoading) {
        return <output aria-live="polite">Loading session...</output>
    }

    const shouldShowNotFound = isNotFound || isNotFoundErrorMessage(error)
    if (shouldShowNotFound) {
        return <SessionNotFound />
    }

    if (!session) {
        return null
    }

    return <SessionDetailByIdContent session={session} />
}
