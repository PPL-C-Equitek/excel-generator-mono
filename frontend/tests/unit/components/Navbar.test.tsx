import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Navbar from '../../../src/components/Navbar'

describe('Navbar', () => {
    // Positive tests
    describe('positive', () => {
        it('renders brand name EQUITEK', () => {
            render(<Navbar />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('renders Login link', () => {
            render(<Navbar />)
            expect(screen.getByText('Login')).toBeInTheDocument()
        })

        it('renders Register link', () => {
            render(<Navbar />)
            expect(screen.getByText('Register')).toBeInTheDocument()
        })

        it('Login links to /login', () => {
            render(<Navbar />)
            expect(screen.getByText('Login')).toHaveAttribute('href', '/login')
        })

        it('Register links to /register', () => {
            render(<Navbar />)
            expect(screen.getByText('Register')).toHaveAttribute('href', '/register')
        })

        it('renders nav element as wrapper', () => {
            render(<Navbar />)
            expect(screen.getByRole('navigation')).toBeInTheDocument()
        })
    })

    // Negative tests
    describe('negative', () => {
        it('does not render a Logout button', () => {
            render(<Navbar />)
            expect(screen.queryByText('Logout')).not.toBeInTheDocument()
        })

        it('does not render a sidebar menu', () => {
            render(<Navbar />)
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByText('History')).not.toBeInTheDocument()
        })

        it('does not render any button element', () => {
            render(<Navbar />)
            expect(screen.queryByRole('button')).not.toBeInTheDocument()
        })

        it('does not render empty brand name', () => {
            render(<Navbar />)
            const brand = screen.getByText('EQUITEK')
            expect(brand.textContent).not.toBe('')
        })
    })
})