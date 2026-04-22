import { render, screen, fireEvent } from '@testing-library/react'
import FeedbackMessage from '@/components/FeedbackMessage'
import { describe, it, expect } from 'vitest'
import { vi } from 'vitest'

describe('FeedbackMessage', () => {

    // Positive

    describe('Positive cases', () => {
        it('renders message text correctly', () => {
            render(<FeedbackMessage message="Data berhasil disimpan." />)
            expect(screen.getByText('Data berhasil disimpan.')).toBeInTheDocument()
        })

        it('defaults to info variant when variant is not provided', () => {
            render(<FeedbackMessage message="Info message" />)
            const el = screen.getByRole('status')
            expect(el).toBeInTheDocument()
        })

        it.each(['success', 'info'] as const)(
            '%s variant uses role="status"',
            (variant) => {
                render(<FeedbackMessage message="Test" variant={variant} />)
                expect(screen.getByRole('status')).toBeInTheDocument()
            }
        )

        it.each(['warning', 'error'] as const)(
            '%s variant uses role="alert"',
            (variant) => {
                render(<FeedbackMessage message="Test" variant={variant} />)
                expect(screen.getByRole('alert')).toBeInTheDocument()
            }
        )

        it('applies custom className', () => {
            render(<FeedbackMessage message="Test" className="mb-4" />)
            const el = screen.getByRole('status')
            expect(el).toHaveClass('mb-4')
        })

        it('renders dismiss button when dismissible=true', () => {
            render(
                <FeedbackMessage
                    message="Test"
                    dismissible
                    onDismiss={() => { }}
                />
            )
            expect(screen.getByRole('button', { name: /tutup/i })).toBeInTheDocument()
        })

        it('calls onDismiss when dismiss button is clicked', () => {
            const onDismiss = vi.fn()
            render(
                <FeedbackMessage
                    message="Test"
                    dismissible
                    onDismiss={onDismiss}
                />
            )
            fireEvent.click(screen.getByRole('button', { name: /tutup/i }))
            expect(onDismiss).toHaveBeenCalledTimes(1)
        })

        it('renders all four variants without crashing', () => {
            const variants = ['success', 'warning', 'error', 'info'] as const

            variants.forEach((variant) => {
                const { unmount } = render(
                    <FeedbackMessage message="Test" variant={variant} />
                )

                expect(screen.getByText('Test')).toBeInTheDocument()

                unmount()
            })
        })
    })

    // Negative

    describe('Negative cases', () => {
        it('does not render dismiss button when dismissible is not provided', () => {
            render(<FeedbackMessage message="Test" />)
            expect(screen.queryByRole('button', { name: /tutup/i })).not.toBeInTheDocument()
        })

        it('does not render dismiss button when dismissible=false', () => {
            render(<FeedbackMessage message="Test" dismissible={false} />)
            expect(screen.queryByRole('button', { name: /tutup/i })).not.toBeInTheDocument()
        })

        it('does not throw when onDismiss is not provided but dismissible=true', () => {
            render(<FeedbackMessage message="Test" dismissible />)
            const btn = screen.getByRole('button', { name: /tutup/i })
            expect(() => fireEvent.click(btn)).not.toThrow()
        })

        it('does not call onDismiss when dismiss button is not rendered', () => {
            const onDismiss = vi.fn()
            render(<FeedbackMessage message="Test" onDismiss={onDismiss} />)
            expect(onDismiss).not.toHaveBeenCalled()
        })

        it('does not apply extra class when className is empty string', () => {
            render(<FeedbackMessage message="Test" className="" />)
            const el = screen.getByRole('status')
            expect(el.className.trim()).not.toContain('  ')
        })
    })

    // Edge Case

    describe('Edge cases', () => {
        it('renders very long message without breaking layout', () => {
            const longMessage = 'A'.repeat(500)
            render(<FeedbackMessage message={longMessage} />)
            expect(screen.getByText(longMessage)).toBeInTheDocument()
        })

        it('renders message with special characters', () => {
            const specialMsg = '<script>alert("xss")</script>'
            render(<FeedbackMessage message={specialMsg} />)
            expect(screen.getByText(specialMsg)).toBeInTheDocument()
            expect(document.querySelector('script')).toBeNull()
        })

        it('renders message with unicode and emoji-like characters', () => {
            const unicodeMsg = '✓ Berhasil disimpan — düsseldorf & co.'
            render(<FeedbackMessage message={unicodeMsg} />)
            expect(screen.getByText(unicodeMsg)).toBeInTheDocument()
        })

        it('renders correctly with empty string message', () => {
            expect(() => render(<FeedbackMessage message="" />)).not.toThrow()
            expect(screen.getByRole('status')).toBeInTheDocument()
        })

        it('onDismiss is only called once per click, not multiple times', () => {
            const onDismiss = vi.fn()
            render(
                <FeedbackMessage
                    message="Test"
                    dismissible
                    onDismiss={onDismiss}
                />
            )
            const btn = screen.getByRole('button', { name: /tutup/i })
            fireEvent.click(btn)
            fireEvent.click(btn)
            expect(onDismiss).toHaveBeenCalledTimes(2)
        })

        it('re-renders correctly when variant prop changes', () => {
            const { rerender } = render(
                <FeedbackMessage message="Test" variant="info" />
            )
            expect(screen.getByRole('status')).toBeInTheDocument()

            rerender(<FeedbackMessage message="Test" variant="error" />)
            expect(screen.getByRole('alert')).toBeInTheDocument()
        })

        it('re-renders with updated message text', () => {
            const { rerender } = render(
                <FeedbackMessage message="Pesan awal" variant="info" />
            )
            expect(screen.getByText('Pesan awal')).toBeInTheDocument()

            rerender(<FeedbackMessage message="Pesan baru" variant="info" />)
            expect(screen.getByText('Pesan baru')).toBeInTheDocument()
            expect(screen.queryByText('Pesan awal')).not.toBeInTheDocument()
        })

        it('applies both default and custom classes without duplication', () => {
            render(<FeedbackMessage message="Test" className="custom-class" />)
            const el = screen.getByRole('status')
            expect(el).toHaveClass('custom-class')
            expect(el).toHaveClass('feedback-message')
        })
    })
})