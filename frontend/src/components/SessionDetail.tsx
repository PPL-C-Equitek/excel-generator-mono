'use client'

import { useSessionResume } from '@/hooks/useSessionResume'
import type { SessionResume, SessionResumeHistoryItem } from '@/services/sessions'

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

function isSessionDetailByIdProps(
    props: Readonly<SessionDetailProps>
): props is SessionDetailByIdProps {
    return 'sessionId' in props
}

function isNotFoundErrorMessage(error: string | null): boolean {
    if (!error) {
        return false
    }

    const normalized = error.trim().toLowerCase()
    return normalized === 'not found.' || normalized.includes('not found') || normalized.includes('404')
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

function getPrimaryPrompt(session: SessionResume): string {
    const firstUserMessage = session.history.find(
        (item): item is Extract<SessionResumeHistoryItem, { type: 'message' }> =>
            item.type === 'message' && item.role === 'user' && item.content.trim().length > 0
    )

    if (firstUserMessage) {
        return firstUserMessage.content
    }

    return session.title
}

function buildSessionMetrics(session: SessionResume) {
    const userPrompts = session.history.filter(
        (item) => item.type === 'message' && item.role === 'user'
    ).length
    const assistantReplies = session.history.filter(
        (item) => item.type === 'message' && item.role === 'assistant'
    ).length
    const outputs = session.history.filter((item) => item.type === 'output').length

    return {
        totalEvents: session.history.length,
        userPrompts,
        assistantReplies,
        outputs,
    }
}

function SessionNotFound() {
    return (
        <section
            role="status"
            aria-live="polite"
            className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-800"
        >
            <h1 className="text-lg font-semibold">Sesi Tidak Ditemukan</h1>
        </section>
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

    return (
        <article className="flex justify-start">
            <div className="max-w-4xl rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                    AI Output
                </p>
                <div className="break-words overflow-hidden rounded-xl border border-slate-200 bg-slate-950">
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

function SessionHistoryList({ session }: Readonly<{ session: SessionResume }>) {
    if (session.history.length === 0) {
        return (
            <section className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                No conversation history yet.
            </section>
        )
    }

    return (
        <section className="space-y-4" aria-label="Session Conversation">
            {session.history.map((item) =>
                item.type === 'message' ? (
                    <SessionMessageBubble key={`${item.type}-${item.id}`} item={item} />
                ) : (
                    <SessionOutputBubble key={`${item.type}-${item.id}`} item={item} />
                )
            )}
        </section>
    )
}

function SessionDetailByIdContent({ session }: Readonly<{ session: SessionResume }>) {
    const metrics = buildSessionMetrics(session)
    const primaryPrompt = getPrimaryPrompt(session)

    return (
        <article className="space-y-5" aria-labelledby="session-detail-title">
            <header className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                    Session Detail
                </p>
                <h1 id="session-detail-title" className="text-xl font-bold text-slate-900">
                    {session.title}
                </h1>
                <p className="text-sm text-slate-500">{session.id}</p>
            </header>

            <section className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                    Prompt
                </p>
                <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm text-slate-800">
                    {primaryPrompt}
                </p>
            </section>

            <section className="grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                        Metadata
                    </p>
                    <dl className="mt-2 space-y-1 text-sm text-slate-700">
                        <div className="flex justify-between gap-3">
                            <dt>Created At</dt>
                            <dd>{formatSessionDate(session.created_at)}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>Updated At</dt>
                            <dd>{formatSessionDate(session.updated_at)}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>Last Message</dt>
                            <dd>{formatSessionDate(session.last_message_at)}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>Last Output</dt>
                            <dd>{formatSessionDate(session.last_output_at)}</dd>
                        </div>
                    </dl>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                        Metrics
                    </p>
                    <dl className="mt-2 space-y-1 text-sm text-slate-700">
                        <div className="flex justify-between gap-3">
                            <dt>Total Events</dt>
                            <dd>{metrics.totalEvents}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>User Prompts</dt>
                            <dd>{metrics.userPrompts}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>Assistant Replies</dt>
                            <dd>{metrics.assistantReplies}</dd>
                        </div>
                        <div className="flex justify-between gap-3">
                            <dt>AI Outputs</dt>
                            <dd>{metrics.outputs}</dd>
                        </div>
                    </dl>
                </div>
            </section>

            <SessionHistoryList session={session} />
        </article>
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
    if (!isSessionDetailByIdProps(props)) {
        return <SessionDetailLegacyContent session={props.session} isNotFound={props.isNotFound} />
    }

    const { session, isLoading, isNotFound, error } = useSessionResume(props.sessionId)

    if (isLoading) {
        return <section role="status">Loading session...</section>
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
