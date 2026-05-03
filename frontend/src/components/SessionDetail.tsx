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

function formatHistoryItem(item: SessionResumeHistoryItem): string {
    if (item.type === 'message') {
        return `${item.role.toUpperCase()}: ${item.content}`
    }

    return `OUTPUT:\n${JSON.stringify(item.output_json, null, 2)}`
}

function mapResumeToSession(resume: SessionResume | null): Session | null {
    if (!resume) {
        return null
    }

    const totalItems = resume.history.length

    return {
        id: resume.id,
        prompt: resume.title,
        score: totalItems,
        evaluatedAt: resume.updated_at,
        output: resume.history.map(formatHistoryItem).join('\n\n'),
    }
}

function SessionDetailContent({
    session,
    isNotFound,
}: Readonly<SessionDetailStateProps>) {
    if (isNotFound) {
        return (
            <section role="status" aria-live="polite">
                <h1>Sesi Tidak Ditemukan</h1>
            </section>
        )
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
                <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-950">
                    <pre className="max-h-96 overflow-x-auto p-4 text-xs leading-6 text-slate-100">
                        <p className="break-words [overflow-wrap:anywhere] whitespace-pre-wrap">
                            {session.output}
                        </p>
                    </pre>
                </div>
            </section>
        </article>
    )
}

export default function SessionDetail(props: Readonly<SessionDetailProps>) {
    if (!isSessionDetailByIdProps(props)) {
        return <SessionDetailContent session={props.session} isNotFound={props.isNotFound} />
    }

    const { session, isLoading, isNotFound, error } = useSessionResume(props.sessionId)

    if (isLoading) {
        return <section role="status">Loading session...</section>
    }

    const mappedSession = mapResumeToSession(session)
    const shouldShowNotFound = isNotFound || Boolean(error)

    return <SessionDetailContent session={mappedSession} isNotFound={shouldShowNotFound} />
}
