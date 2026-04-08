import { render, screen } from '@testing-library/react'
import { beforeEach, describe, it, expect } from 'vitest'
import { vi } from 'vitest'
import Navbar from '../../../src/components/Navbar'
import type { NavLink } from '../../../src/constants/landing'

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

// Mock data for testing - demonstrates DIP principle
const mockNavLinks: NavLink[] = [
    { label: 'Login', href: '/login', key: 'login' },
    { label: 'Register', href: '/register', key: 'register' },
]

describe('Navbar', () => {
    beforeEach(() => {
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    // Positive tests
    describe('positive', () => {
        it('renders brand name EQUITEK by default', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('links brand name to home', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('EQUITEK')).toHaveAttribute('href', '/')
        })

        it('renders custom brand name when provided', () => {
            render(<Navbar links={mockNavLinks} brandName="CUSTOM BRAND" />)
            expect(screen.getByText('CUSTOM BRAND')).toBeInTheDocument()
        })

        it('renders provided navigation links', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Login')).toBeInTheDocument()
            expect(screen.getByText('Register')).toBeInTheDocument()
        })

        it('Login links to /login', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Login')).toHaveAttribute('href', '/login')
        })

        it('Register links to /register', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByText('Register')).toHaveAttribute('href', '/register')
        })

        it('renders nav element as wrapper', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.getByRole('navigation')).toBeInTheDocument()
        })

        it('renders custom links when different NavLink array provided', () => {
            const customLinks: NavLink[] = [
                { label: 'Home', href: '/', key: 'login' },
                { label: 'About', href: '/about', key: 'register' },
            ]
            render(<Navbar links={customLinks} />)
            expect(screen.getByText('Home')).toBeInTheDocument()
            expect(screen.getByText('About')).toBeInTheDocument()
            expect(screen.queryByText('Login')).not.toBeInTheDocument()
        })
    })

    // Negative tests
    describe('negative', () => {
        it('does not render a Logout button', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByText('Logout')).not.toBeInTheDocument()
        })

        it('does not render a sidebar menu', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByText('History')).not.toBeInTheDocument()
        })

        it('does not render any button element', () => {
            render(<Navbar links={mockNavLinks} />)
            expect(screen.queryByRole('button')).not.toBeInTheDocument()
        })

        it('does not render empty brand name', () => {
            render(<Navbar links={mockNavLinks} />)
            const brand = screen.getByText('EQUITEK')
            expect(brand.textContent).not.toBe('')
        })

        it('does not render links that are not in the provided array', () => {
            const minimalLinks: NavLink[] = [
                { label: 'Home', href: '/', key: 'login' }
            ]
            render(<Navbar links={minimalLinks} />)
            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
        })

        it('does not render Login and Register links when user is already authenticated', () => {
            window.localStorage.setItem('access_token', 'existing-token')

            render(<Navbar links={mockNavLinks} />)

            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
            expect(screen.getByText('Convert')).toBeInTheDocument()
            expect(screen.getByText('Schema')).toBeInTheDocument()
            expect(screen.getByText('History')).toBeInTheDocument()
            expect(screen.queryByText('Change Password')).not.toBeInTheDocument()
            expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
        })
    })
})
