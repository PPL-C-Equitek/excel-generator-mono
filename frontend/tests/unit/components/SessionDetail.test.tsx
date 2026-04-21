import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import SessionDetail from '../../../src/components/SessionDetail'

// RED phase reminder: run `npm run test` and confirm this suite fails because `SessionDetail` does not exist yet.

type SessionDetailProps = React.ComponentProps<typeof SessionDetail>

describe('SessionDetail', () => {
    const validSession: NonNullable<SessionDetailProps['session']> = {
        id: 'session-001',
        prompt: 'Bandingkan performa GPT-4.1 dan Claude pada benchmark reasoning.',
        score: 92.5,
        evaluatedAt: '2026-04-22T09:30:00.000Z',
        output: `| model | score |
| ----- | ----- |
| GPT-4.1 | 92.5 |
| Claude | 90.1 |

const extremelyLongLine = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";`,
    }

    const getOutputElement = () =>
        screen.getByText((_, element) =>
            element?.tagName.toLowerCase() === 'p' &&
            element.textContent === validSession.output
        )

    describe('negative', () => {
        it('renders "Sesi Tidak Ditemukan" when isNotFound is true', () => {
            render(<SessionDetail session={null} isNotFound />)

            expect(screen.getByText('Sesi Tidak Ditemukan')).toBeInTheDocument()
            expect(
                screen.queryByText(validSession.prompt)
            ).not.toBeInTheDocument()
        })
    })

    describe('positive', () => {
        it('renders prompt, score, evaluatedAt, and output when valid session data is provided', () => {
            render(<SessionDetail session={validSession} isNotFound={false} />)

            expect(screen.getByText(validSession.prompt)).toBeInTheDocument()
            expect(screen.getByText(String(validSession.score))).toBeInTheDocument()
            expect(screen.getByText(validSession.evaluatedAt)).toBeInTheDocument()
            expect(getOutputElement()).toBeInTheDocument()
        })

        it('renders metadata for the session id alongside the rest of the session information', () => {
            render(<SessionDetail session={validSession} isNotFound={false} />)

            expect(screen.getByText(validSession.id)).toBeInTheDocument()
        })
    })

    describe('edge cases', () => {
        it('applies overflow protection classes to the output container', () => {
            render(<SessionDetail session={validSession} isNotFound={false} />)

            const outputElement = getOutputElement()
            const outputContainer = outputElement.closest('div')

            expect(outputContainer).not.toBeNull()
            expect(outputContainer).toHaveClass('overflow-x-auto')
            expect(outputElement).toHaveClass('break-words')
            expect(outputElement).toHaveClass('whitespace-pre-wrap')
        })
    })
})
