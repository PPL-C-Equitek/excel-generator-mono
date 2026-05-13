import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import LoginForm from '../../../src/components/LoginForm'

function renderLoginForm(overrides: Partial<React.ComponentProps<typeof LoginForm>> = {}) {
    const props: React.ComponentProps<typeof LoginForm> = {
        onSubmit: vi.fn(),
        onGoogleSignIn: vi.fn(),
        isLoading: false,
        apiError: null,
        onClearApiError: vi.fn(),
        ...overrides,
    }

    return {
        ...render(<LoginForm {...props} />),
        props,
    }
}

describe('LoginForm', () => {
    it('renders login heading and supporting copy', () => {
        renderLoginForm()

        expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument()
        expect(screen.getByText(/sign in to continue to your workspace/i)).toBeInTheDocument()
    })

    it('renders email input with correct placeholder', () => {
        renderLoginForm()

        const emailInput = screen.getByLabelText(/email/i)
        expect(emailInput).toHaveAttribute('placeholder', 'Enter your email')
        expect(emailInput).toHaveAttribute('type', 'email')
    })

    it('renders password input with correct placeholder', () => {
        renderLoginForm()

        const passwordInput = screen.getByTestId('password-input')
        expect(passwordInput).toHaveAttribute('placeholder', 'Enter your password')
        expect(passwordInput).toHaveAttribute('type', 'password')
    })

    it('calls submit handler when sign in is clicked with valid data', async () => {
        const { props } = renderLoginForm()

        await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
        await userEvent.type(screen.getByTestId('password-input'), 'password123')
        await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(props.onSubmit).toHaveBeenCalledTimes(1)
        expect(props.onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({
                email: 'test@example.com',
                password: 'password123',
            })
        )
    })

    it('calls google sign-in handler when google button is clicked', async () => {
        const { props } = renderLoginForm()

        await userEvent.click(screen.getByRole('button', { name: /sign in with google/i }))

        expect(props.onGoogleSignIn).toHaveBeenCalledTimes(1)
    })

    it('displays api error message when provided', () => {
        renderLoginForm({
            apiError: 'Invalid credentials',
        })

        expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
    })

    it('displays validation error for missing email', async () => {
        renderLoginForm()

        await userEvent.type(screen.getByTestId('password-input'), 'password123')
        await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(screen.getByRole('alert')).toHaveTextContent('Please enter a valid email address.')
    })

    it('displays validation error for invalid email format', async () => {
        renderLoginForm()

        await userEvent.type(screen.getByLabelText(/email/i), 'invalid-email')
        await userEvent.type(screen.getByTestId('password-input'), 'password123')
        await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(screen.getByRole('alert')).toHaveTextContent('Please enter a valid email address.')
    })

    it('displays validation error for missing password', async () => {
        renderLoginForm()

        await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
        await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(screen.getByRole('alert')).toHaveTextContent('Password is required.')
    })

    it('disables inputs and buttons when loading', () => {
        renderLoginForm({ isLoading: true })

        expect(screen.getByTestId('password-input')).toBeDisabled()
        expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled()
        expect(screen.getByRole('button', { name: /google/i })).toBeDisabled()
    })

    it('shows loading labels when loading', () => {
        renderLoginForm({ isLoading: true })

        expect(screen.getByText('Signing In...')).toBeInTheDocument()
    })

    it('renders forgot password link', () => {
        renderLoginForm()

        const forgotLink = screen.getByRole('link', { name: /forgot password/i })
        expect(forgotLink).toHaveAttribute('href', '/forgot-password')
    })

    it('renders sign up link', () => {
        renderLoginForm()

        const signupLink = screen.getByRole('link', { name: /sign up for free/i })
        expect(signupLink).toHaveAttribute('href', '/register')
    })

    it('clears api error when user starts typing email', async () => {
        const { props } = renderLoginForm({
            apiError: 'Invalid credentials',
        })

        expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')

        await userEvent.type(screen.getByLabelText(/email/i), 'a')

        expect(props.onClearApiError).toHaveBeenCalled()
    })

    it('clears api error when user starts typing password', async () => {
        const { props } = renderLoginForm({
            apiError: 'Invalid credentials',
        })

        expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')

        await userEvent.type(screen.getByTestId('password-input'), 'a')

        expect(props.onClearApiError).toHaveBeenCalled()
    })

    it('renders blue focus ring on inputs', () => {
        renderLoginForm()

        const emailInput = screen.getByLabelText(/email/i)
        expect(emailInput).toHaveClass('focus:ring-2', 'focus:ring-blue-600')

        const passwordInput = screen.getByTestId('password-input')
        expect(passwordInput).toHaveClass('focus:ring-2', 'focus:ring-blue-600')
    })

    it('renders blue focus ring on submit button', () => {
        renderLoginForm()

        const submitButton = screen.getByRole('button', { name: /^sign in$/i })
        expect(submitButton).toHaveClass('focus:ring-2', 'focus:ring-blue-600')
    })
})
