import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HeroSection from '../../../src/components/HeroSection'

describe('HeroSection', () => {
    // Positive tests
    describe('positive', () => {
        it('renders default heading', () => {
            render(<HeroSection />)
            expect(screen.getByText(/Automated Intelligence/i)).toBeInTheDocument()
        })

        it('renders default subtitle', () => {
            render(<HeroSection />)
            expect(screen.getByText(/Empowering your workflow/i)).toBeInTheDocument()
        })

        it('renders custom heading when provided', () => {
            render(<HeroSection heading="Custom Heading" />)
            expect(screen.getByText('Custom Heading')).toBeInTheDocument()
        })

        it('renders custom subtitle when provided', () => {
            render(<HeroSection subtitle="Custom subtitle text" />)
            expect(screen.getByText('Custom subtitle text')).toBeInTheDocument()
        })

        it('renders hero section with correct testid', () => {
            render(<HeroSection />)
            expect(screen.getByTestId('hero-section')).toBeInTheDocument()
        })

        it('renders dark overlay', () => {
            render(<HeroSection />)
            expect(screen.getByTestId('hero-overlay')).toBeInTheDocument()
        })

        it('applies background image when provided', () => {
            render(<HeroSection backgroundImage="/custom-bg.jpg" />)
            const hero = screen.getByTestId('hero-section')
            expect(hero).toHaveStyle("background-image: url('/custom-bg.jpg')")
        })
    })

    // Negative tests
    describe('negative', () => {
        it('does not render a button', () => {
            render(<HeroSection />)
            expect(screen.queryByRole('button')).not.toBeInTheDocument()
        })

        it('does not render default heading when custom heading is given', () => {
            render(<HeroSection heading="Custom Heading" />)
            expect(
                screen.queryByText(/Automated Intelligence/i)
            ).not.toBeInTheDocument()
        })

        it('does not render default subtitle when custom subtitle is given', () => {
            render(<HeroSection subtitle="Custom subtitle" />)
            expect(
                screen.queryByText(/Empowering your workflow/i)
            ).not.toBeInTheDocument()
        })

        it('does not render navigation links', () => {
            render(<HeroSection />)
            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
        })

        it('does not render empty heading', () => {
            render(<HeroSection />)
            const heading = screen.getByRole('heading', { level: 1 })
            expect(heading.textContent).not.toBe('')
        })
    })
})