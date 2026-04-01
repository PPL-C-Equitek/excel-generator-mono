import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import LoginForm from '../../../src/components/LoginForm'

describe('LoginForm', () => {
    // POSITIVE
    describe('positive', () => {
        it('renders Login heading', () => {
            render(<LoginForm />)
            expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument()
        })

        it('renders subtitle text', () => {
            render(<LoginForm />)
            expect(
                screen.getByText(/Welcome back! Please enter your details/i)
            ).toBeInTheDocument()
        })

        it('renders email label and input', () => {
            render(<LoginForm />)
            expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
            expect(screen.getByPlaceholderText(/enter your email/i)).toBeInTheDocument()
        })

        it('renders password label and input', () => {
            render(<LoginForm />)
            expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
            expect(screen.getByTestId('password-input')).toHaveAttribute('type', 'password')
        })

        it('renders Remember me checkbox', () => {
            render(<LoginForm />)
            expect(screen.getByLabelText(/remember me/i)).toBeInTheDocument()
            expect(screen.getByLabelText(/remember me/i)).toHaveAttribute('type', 'checkbox')
        })

        it('renders Forgot password link', () => {
            render(<LoginForm />)
            expect(screen.getByText(/forgot password/i)).toBeInTheDocument()
        })

        it('renders Sign in button', () => {
            render(<LoginForm />)
            expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument()
        })

        it('renders Sign in with Google button', () => {
            render(<LoginForm />)
            expect(
                screen.getByRole('button', { name: /sign in with google/i })
            ).toBeInTheDocument()
        })

        it('renders Sign up for free link', () => {
            render(<LoginForm />)
            expect(screen.getByText(/sign up for free/i)).toBeInTheDocument()
        })

        it('updates email field on user input', async () => {
            render(<LoginForm />)
            const emailInput = screen.getByLabelText(/email/i)
            await userEvent.type(emailInput, 'test@example.com')
            expect(emailInput).toHaveValue('test@example.com')
        })

        it('updates password field on user input', async () => {
            render(<LoginForm />)
            const passwordInput = screen.getByTestId('password-input')
            await userEvent.type(passwordInput, 'secret123')
            expect(passwordInput).toHaveValue('secret123')
        })

        it('toggles remember me checkbox', async () => {
            render(<LoginForm />)
            const checkbox = screen.getByLabelText(/remember me/i)
            expect(checkbox).not.toBeChecked()
            await userEvent.click(checkbox)
            expect(checkbox).toBeChecked()
        })

        it('calls onSubmit with email and password when Sign in clicked', async () => {
            const mockOnSubmit = vi.fn()
            render(<LoginForm onSubmit={mockOnSubmit} />)

            await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
            await userEvent.type(screen.getByTestId('password-input'), 'secret123')
            await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))

            await waitFor(() => {
                expect(mockOnSubmit).toHaveBeenCalledWith({
                    email: 'test@example.com',
                    password: 'secret123',
                    rememberMe: false,
                })
            })
        })

        it('calls onGoogleSignIn when Sign in with Google clicked', async () => {
            const mockOnGoogleSignIn = vi.fn()
            render(<LoginForm onGoogleSignIn={mockOnGoogleSignIn} />)
            await userEvent.click(
                screen.getByRole('button', { name: /sign in with google/i })
            )
            expect(mockOnGoogleSignIn).toHaveBeenCalledTimes(1)
        })
    })

    // NEGATIVE
    describe('negative', () => {
        it('does not render register form fields', () => {
            render(<LoginForm />)
            expect(screen.queryByLabelText(/confirm password/i)).not.toBeInTheDocument()
            expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument()
        })

        it('does not call onSubmit when fields are empty', async () => {
            const mockOnSubmit = vi.fn()
            render(<LoginForm onSubmit={mockOnSubmit} />)
            await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))
            expect(mockOnSubmit).not.toHaveBeenCalled()
        })

        it('shows error when email is invalid', async () => {
            render(<LoginForm />)
            await userEvent.type(screen.getByLabelText(/email/i), 'invalid-email')
            await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))
            expect(screen.getByRole('alert')).toBeInTheDocument()
        })

        it('shows error when password is empty', async () => {
            render(<LoginForm />)
            await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
            await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }))
            expect(screen.getByRole('alert')).toBeInTheDocument()
        })

        it('does not show error on initial render', () => {
            render(<LoginForm />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        })
    })
})