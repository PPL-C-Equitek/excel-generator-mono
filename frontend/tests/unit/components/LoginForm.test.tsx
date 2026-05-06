import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import LoginForm from '../../../src/components/LoginForm'

function renderLoginForm(overrides: Partial<React.ComponentProps<typeof LoginForm>> = {}) {
    const props: React.ComponentProps<typeof LoginForm> = {
        email: '',
        password: '',
        onEmailChange: vi.fn(),
        onPasswordChange: vi.fn(),
        onSubmit: vi.fn(),
        onGoogleSignIn: vi.fn(),
        errorMessage: null,
        onDismissError: vi.fn(),
        successMessage: null,
        onDismissSuccess: vi.fn(),
        isLoading: false,
        isDisabled: false,
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

    it('renders controlled input values', () => {
        renderLoginForm({
            email: 'test@example.com',
            password: 'secret123',
        })

        expect(screen.getByLabelText(/email/i)).toHaveValue('test@example.com')
        expect(screen.getByTestId('password-input')).toHaveValue('secret123')
    })

    it('forwards email and password changes', async () => {
        const { props } = renderLoginForm()

        await userEvent.type(screen.getByLabelText(/email/i), 'a')
        await userEvent.type(screen.getByTestId('password-input'), 'b')

        expect(props.onEmailChange).toHaveBeenCalled()
        expect(props.onPasswordChange).toHaveBeenCalled()
    })

    it('calls submit handler when sign in is clicked', async () => {
        const { props } = renderLoginForm()

        await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

        expect(props.onSubmit).toHaveBeenCalledTimes(1)
    })

    it('calls google sign-in handler when google button is clicked', async () => {
        const { props } = renderLoginForm()

        await userEvent.click(screen.getByRole('button', { name: /sign in with google/i }))

        expect(props.onGoogleSignIn).toHaveBeenCalledTimes(1)
    })

    it('renders error and success feedback from props', () => {
        renderLoginForm({
            errorMessage: 'Invalid credentials',
            successMessage: 'Welcome back!',
        })

        expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
        expect(screen.getByText('Welcome back!')).toBeInTheDocument()
    })

    it('disables inputs and buttons when disabled', () => {
        renderLoginForm({ isDisabled: true })

        expect(screen.getByLabelText(/email/i)).toBeDisabled()
        expect(screen.getByTestId('password-input')).toBeDisabled()
        expect(screen.getByRole('button', { name: /^sign in$/i })).toBeDisabled()
        expect(screen.getByRole('button', { name: /sign in with google/i })).toBeDisabled()
    })

    it('shows loading labels when loading', () => {
        renderLoginForm({ isLoading: true })

        expect(screen.getAllByText('Signing in...')).toHaveLength(2)
    })
})
