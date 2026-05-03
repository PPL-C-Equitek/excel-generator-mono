import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SessionDetail, { type Session as SessionDetailData } from '@/components/SessionDetail'
import { useSessionResume } from '@/hooks/useSessionResume'
import { getSessionResume, type SessionResume } from '@/services/sessions'

vi.mock('@/services/sessions', () => ({
    getSessionResume: vi.fn(),
}))

const mockGetSessionResume = vi.mocked(getSessionResume)

function mapSessionResumeToDetailSession(
    sessionResume: SessionResume | null
): SessionDetailData | null {
    if (!sessionResume) {
        return null
    }

    return {
        id: sessionResume.id,
        prompt: sessionResume.title,
        score: 0,
        evaluatedAt: sessionResume.updated_at,
        output: JSON.stringify(sessionResume.history, null, 2),
    }
}

function SessionDetailContainer({ sessionId }: { sessionId: string | null }) {
    const { session, isLoading, isNotFound } = useSessionResume(sessionId)

    if (isLoading) {
        return <section role="status">Loading session...</section>
    }

    return (
        <SessionDetail
            session={mapSessionResumeToDetailSession(session)}
            isNotFound={isNotFound}
        />
    )
}

describe('SessionDetail (RED)', () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it('renders loading state while waiting for /sessions/{id}/resume', async () => {
        let resolveRequest: ((value: SessionResume) => void) | null = null
        mockGetSessionResume.mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolveRequest = resolve
                })
        )

        render(<SessionDetailContainer sessionId="session-001" />)

        expect(screen.getByText('Loading session...')).toBeInTheDocument()

        resolveRequest?.({
            id: 'session-001',
            title: 'Prompt from API',
            created_at: '2026-04-22T09:30:00.000Z',
            updated_at: '2026-04-22T09:31:00.000Z',
            last_message_at: null,
            last_output_at: null,
            history: [],
        })

        await waitFor(() => {
            expect(screen.getByText('Prompt from API')).toBeInTheDocument()
        })
    })

    it.each([
        { label: '404', errorMessage: 'Not found.' },
        { label: '403', errorMessage: 'Forbidden.' },
    ])(
        'renders "Sesi Tidak Ditemukan" fallback for resume API error $label',
        async ({ errorMessage }) => {
            mockGetSessionResume.mockRejectedValueOnce(new Error(errorMessage))

            render(<SessionDetailContainer sessionId={`session-${errorMessage}`} />)

            await waitFor(() => {
                expect(screen.getByText('Sesi Tidak Ditemukan')).toBeInTheDocument()
            })
        }
    )

    it('keeps response content wrapped for long code blocks and huge table rows', () => {
        const output = `|col1|col2|
|----|----|
|${'A'.repeat(500)}|${'B'.repeat(500)}|
const row = "${'x'.repeat(1000)}"`

        render(
            <SessionDetail
                session={{
                    id: 'session-edge',
                    prompt: 'Render long output safely',
                    score: 98,
                    evaluatedAt: '2026-04-22T09:30:00.000Z',
                    output,
                }}
                isNotFound={false}
            />
        )

        const outputSection = screen.getByLabelText('Session Output')
        const outputText = outputSection.querySelector('p')
        const outputContainer = outputText?.closest('div')

        expect(outputText).not.toBeNull()
        expect(outputContainer).not.toBeNull()
        expect(outputContainer).toHaveClass('overflow-x-auto')
        expect(outputText).toHaveClass('break-words')
    })
})
