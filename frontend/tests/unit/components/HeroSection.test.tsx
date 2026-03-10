import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HeroSection from '../../../src/components/HeroSection'
import { LANDING_HERO_CONFIG } from '../../../src/constants/landing'

describe('HeroSection', () => {
    // Positive tests
    describe('positive', () => {
        it('renders default heading from LANDING_HERO_CONFIG', () => {
            render(<HeroSection />)
            expect(screen.getByText(LANDING_HERO_CONFIG.heading)).toBeInTheDocument()
        })

        it('renders default subtitle from LANDING_HERO_CONFIG', () => {
            render(<HeroSection />)
            expect(screen.getByText(LANDING_HERO_CONFIG.subtitle)).toBeInTheDocument()
        })

        it('renders custom heading when provided (OCP)', () => {
            render(<HeroSection heading="Custom Heading" />)
            expect(screen.getByText('Custom Heading')).toBeInTheDocument()
            // default tidak muncul saat override
            expect(
                screen.queryByText(LANDING_HERO_CONFIG.heading)
            ).not.toBeInTheDocument()
        })

        it('renders custom subtitle when provided (OCP)', () => {
            render(<HeroSection subtitle="Custom subtitle text" />)
            expect(screen.getByText('Custom subtitle text')).toBeInTheDocument()
            // default tidak muncul saat override
            expect(
                screen.queryByText(LANDING_HERO_CONFIG.subtitle)
            ).not.toBeInTheDocument()
        })

        it('renders hero section with correct testid', () => {
            render(<HeroSection />)
            expect(screen.getByTestId('hero-section')).toBeInTheDocument()
        })

        it('renders dark overlay', () => {
            render(<HeroSection />)
            expect(screen.getByTestId('hero-overlay')).toBeInTheDocument()
        })

        it('applies default background image from LANDING_HERO_CONFIG', () => {
            render(<HeroSection />)
            const hero = screen.getByTestId('hero-section')
            expect(hero).toHaveStyle(
                `background-image: url('${LANDING_HERO_CONFIG.backgroundImage}')`
            )
        })

        it('applies custom background image when provided (OCP)', () => {
            render(<HeroSection backgroundImage="/custom-bg.jpg" />)
            const hero = screen.getByTestId('hero-section')
            expect(hero).toHaveStyle("background-image: url('/custom-bg.jpg')")
            // default tidak dipakai saat override
            expect(hero).not.toHaveStyle(
                `background-image: url('${LANDING_HERO_CONFIG.backgroundImage}')`
            )
        })

        it('accepts combination of custom props (ISP)', () => {
            render(
                <HeroSection
                    heading="New Heading"
                    subtitle="New Subtitle"
                    backgroundImage="/images/bg.jpg"
                />
            )
            expect(screen.getByText('New Heading')).toBeInTheDocument()
            expect(screen.getByText('New Subtitle')).toBeInTheDocument()
            expect(screen.getByTestId('hero-section')).toHaveStyle(
                "background-image: url('/images/bg.jpg')"
            )
            // semua default tidak muncul
            expect(
                screen.queryByText(LANDING_HERO_CONFIG.heading)
            ).not.toBeInTheDocument()
            expect(
                screen.queryByText(LANDING_HERO_CONFIG.subtitle)
            ).not.toBeInTheDocument()
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