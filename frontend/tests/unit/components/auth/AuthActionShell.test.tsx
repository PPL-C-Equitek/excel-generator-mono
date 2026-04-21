import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
    AuthActionFormError,
    AuthActionLayout,
    AuthActionLink,
    AuthActionShell,
    AuthActionTitle,
    AuthErrorIcon,
    AuthStatusSpinner,
    AuthSuccessIcon,
} from '../../../../src/components/auth/AuthActionShell'

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

describe('AuthActionShell helpers', () => {
    it('renders shell and layout wrappers with children', () => {
        render(
            <>
                <AuthActionShell>
                    <p>shell child</p>
                </AuthActionShell>
                <AuthActionLayout Navbar={<nav>navbar slot</nav>}>
                    <p>layout child</p>
                </AuthActionLayout>
            </>
        )

        expect(screen.getByText('shell child')).toBeInTheDocument()
        expect(screen.getByText('navbar slot')).toBeInTheDocument()
        expect(screen.getByText('layout child')).toBeInTheDocument()
    })

    it('renders title, form error, icons, spinner, and action links', () => {
        render(
            <>
                <AuthActionTitle>Sample Title</AuthActionTitle>
                <AuthActionFormError>Sample Error</AuthActionFormError>
                <AuthActionLink href="/login">Primary</AuthActionLink>
                <AuthActionLink href="/home" secondary className="custom-class">
                    Secondary
                </AuthActionLink>
                <AuthStatusSpinner />
                <AuthSuccessIcon />
                <AuthErrorIcon />
            </>
        )

        expect(screen.getByText('Sample Title')).toBeInTheDocument()
        expect(screen.getByText('Sample Error')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Primary' })).toHaveAttribute('href', '/login')
        expect(screen.getByRole('link', { name: 'Secondary' })).toHaveAttribute('href', '/home')
        expect(screen.getByText('Secondary')).toHaveClass('custom-class')
    })
})
