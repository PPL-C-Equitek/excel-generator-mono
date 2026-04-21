export interface Session {
    id: string
    prompt: string
    score: number
    evaluatedAt: string
    output: string
}

// Props for rendering either a valid session detail view or a not-found state.
export interface SessionDetailProps {
    session: Session | null
    isNotFound: boolean
}

export default function SessionDetail({
    session,
    isNotFound,
}: Readonly<SessionDetailProps>) {
    if (isNotFound || !session) {
        return (
            <section role="alert" aria-live="polite">
                <h1>Sesi Tidak Ditemukan</h1>
            </section>
        )
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
                <div className="overflow-x-auto">
                    <p className="break-words whitespace-pre-wrap">{session.output}</p>
                </div>
            </section>
        </article>
    )
}
