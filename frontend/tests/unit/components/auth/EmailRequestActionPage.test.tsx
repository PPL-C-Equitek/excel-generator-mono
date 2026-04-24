import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmailRequestActionPage, {
    type EmailRequestActionConfig,
} from '../../../../src/components/auth/EmailRequestActionPage'

const mockShouldSkipEmailResend = vi.fn()
const mockResendEmailActionFlow = vi.fn()
const mockUseResendCooldown = vi.fn()

vi.mock('next/link', () => ({
    default: ({
        href,
        children,
        ...props
    }: Readonly<{ href: string; children: ReactNode }>) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock('@/components/Navbar', () => ({
    default: () => <nav>Mock Navbar</nav>,
}))

vi.mock('@/components/AuthEmailSuccessCard', () => ({
    default: ({
        successMessage,
        secondaryButtonText,
        onSecondaryAction,
        isSecondaryDisabled,
    }: Readonly<{
        successMessage: string
        secondaryButtonText: string
        onSecondaryAction: () => void
        isSecondaryDisabled: boolean
    }>) => (
        <section>
            <p>{successMessage}</p>
            <button
                type="button"
                onClick={onSecondaryAction}
                disabled={isSecondaryDisabled}
            >
                {secondaryButtonText}
            </button>
        </section>
    ),
}))

vi.mock('@/hooks/useResendCooldown', () => ({
    useResendCooldown: (...args: unknown[]) => mockUseResendCooldown(...args),
}))

vi.mock('@/lib/authEmailAction', () => ({
    resendEmailActionFlow: (...args: unknown[]) => mockResendEmailActionFlow(...args),
    shouldSkipEmailResend: (...args: unknown[]) => mockShouldSkipEmailResend(...args),
}))

function createConfig(overrides: Partial<EmailRequestActionConfig> = {}): EmailRequestActionConfig {
    return {
        pageTitle: 'Forgot Password',
        pageDescription: 'Enter your email to continue.',
        emailLabel: 'Email',
        emailPlaceholder: 'name@example.com',
        submitLabel: 'Send Reset Link',
        submitLoadingLabel: 'Sending...',
        requestApi: vi.fn().mockResolvedValue({ message: 'Request sent.' }),
        requestSuccessFallbackMessage: 'Fallback request success',
        requestErrorFallbackMessage: 'Fallback request error',
        resendApi: vi.fn().mockResolvedValue({ message: 'Resent.' }),
        resendCooldownStoragePrefix: 'forgot:',
        resendSuccessFallbackMessage: 'Fallback resend success',
        resendErrorFallbackMessage: 'Fallback resend error',
        resendButtonLabel: () => 'Resend Email',
        resendCooldownSeconds: 60,
        successEmailNotice: <>We sent an email to </>,
        successPrimaryHref: '/login',
        successPrimaryLabel: 'Back to login',
        backLinkPrefix: 'Remembered?',
        backLinkHref: '/login',
        backLinkLabel: 'Sign in',
        validateEmail: (email: string) => {
            const trimmed = email.trim()
            if (!trimmed) {
                return {
                    isValid: false,
                    errors: {
                        email: 'Email is required.',
                        form: '',
                    },
                }
            }

            return {
                isValid: true,
                errors: {
                    email: '',
                    form: '',
                },
            }
        },
        ...overrides,
    }
}

describe('EmailRequestActionPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockShouldSkipEmailResend.mockReturnValue(false)
        mockResendEmailActionFlow.mockResolvedValue(undefined)
        mockUseResendCooldown.mockReturnValue({
            cooldown: 0,
            setCooldown: vi.fn(),
        })
    })

    it('returns early on resend when skip guard is true', async () => {
        const user = userEvent.setup()
        const config = createConfig()
        mockShouldSkipEmailResend.mockReturnValue(true)

        render(<EmailRequestActionPage config={config} />)

        await user.type(screen.getByRole('textbox', { name: /email/i }), 'user@example.com')
        await user.click(screen.getByRole('button', { name: 'Send Reset Link' }))

        expect(await screen.findByText('Request sent.')).toBeInTheDocument()

        await user.click(screen.getByRole('button', { name: 'Resend Email' }))

        expect(mockShouldSkipEmailResend).toHaveBeenCalledWith(
            'user@example.com',
            false,
            0
        )
        expect(mockResendEmailActionFlow).not.toHaveBeenCalled()
    })

    it('calls resendEmailActionFlow when resend guard allows retry', async () => {
        const user = userEvent.setup()
        const config = createConfig()

        render(<EmailRequestActionPage config={config} />)

        await user.type(screen.getByRole('textbox', { name: /email/i }), 'user@example.com')
        await user.click(screen.getByRole('button', { name: 'Send Reset Link' }))

        expect(await screen.findByText('Request sent.')).toBeInTheDocument()
        await user.click(screen.getByRole('button', { name: 'Resend Email' }))

        await waitFor(() => {
            expect(mockResendEmailActionFlow).toHaveBeenCalledTimes(1)
        })
    })
})
