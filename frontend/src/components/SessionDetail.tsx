interface Session {
    id: string
    prompt: string
    score: number
    evaluatedAt: string
    output: string
}

interface SessionDetailProps {
    session: Session | null
    isNotFound: boolean
}

export default function SessionDetail({ session, isNotFound }: SessionDetailProps) {
    if (isNotFound || !session) {
        return <p>Sesi Tidak Ditemukan</p>
    }

    return (
        <section className="space-y-4">
            <div>
                <p>{session.id}</p>
                <p>{session.prompt}</p>
                <p>{session.score}</p>
                <p>{session.evaluatedAt}</p>
            </div>

            <div className="overflow-x-auto">
                <p className="break-words whitespace-pre-wrap">{session.output}</p>
            </div>
        </section>
    )
}
