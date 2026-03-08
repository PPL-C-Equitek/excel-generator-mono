import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import LandingPage from '../../../src/app/landing/LandingPage'

describe('LandingPage', () => {
    // ✅ POSITIVE TESTS
    describe('positive', () => {
        // — Navbar —
        it('renders Navbar with brand name', () => {
            render(<LandingPage />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('renders Login link in navbar', () => {
            render(<LandingPage />)
            expect(screen.getByText('Login')).toBeInTheDocument()
        })

        it('renders Register link in navbar', () => {
            render(<LandingPage />)
            expect(screen.getByText('Register')).toBeInTheDocument()
        })

        // — Hero —
        it('renders HeroSection', () => {
            render(<LandingPage />)
            expect(screen.getByTestId('hero-section')).toBeInTheDocument()
        })

        it('renders hero overlay', () => {
            render(<LandingPage />)
            expect(screen.getByTestId('hero-overlay')).toBeInTheDocument()
        })

        it('renders hero heading text', () => {
            render(<LandingPage />)
            expect(screen.getByText(/Automated Intelligence/i)).toBeInTheDocument()
        })

        it('renders hero subtitle text', () => {
            render(<LandingPage />)
            expect(screen.getByText(/Empowering your workflow/i)).toBeInTheDocument()
        })

        // — Features —
        it('renders Why Use Our Service heading', () => {
            render(<LandingPage />)
            expect(screen.getByText('Why Use Our Service?')).toBeInTheDocument()
        })

        it('renders all 6 feature card titles', () => {
            render(<LandingPage />)
            const titles = [
                'Advanced AI Transformation',
                'Instance Excel Mapping',
                'Verified Logic',
                'Full Traceability',
                'Consultant-Grade Standards',
                'Seamless Automation',
            ]
            titles.forEach((title) => {
                expect(screen.getByText(title)).toBeInTheDocument()
            })
        })

        it('renders all 6 feature card descriptions', () => {
            render(<LandingPage />)
            const descs = [
                /Leverage advanced LLMs/i,
                /Maps messy data/i,
                /Multi-step CoT/i,
                /Each extraction decision/i,
                /Focused on professional methods/i,
                /Replaces slow manual data entry/i,
            ]
            descs.forEach((desc) => {
                expect(screen.getByText(desc)).toBeInTheDocument()
            })
        })

        it('renders features in a grid container', () => {
            render(<LandingPage />)
            const featureHeadings = screen.getAllByRole('heading', { level: 3 })
            expect(featureHeadings).toHaveLength(6)
        })

        // — CTA —
        it('renders CTA section heading', () => {
            render(<LandingPage />)
            expect(
                screen.getByText('Ready to Automate Your Data Workflow?')
            ).toBeInTheDocument()
        })

        it('renders Get Started CTA linking to /convert', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            expect(cta).toBeInTheDocument()
            expect(cta).toHaveAttribute('href', '/convert')
        })

        it('CTA button has correct initial background color', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            expect(cta).toHaveStyle({ backgroundColor: 'var(--brand-primary)' })
        })

        it('CTA button changes color on mouse enter', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            fireEvent.mouseEnter(cta)
            expect(cta).toHaveStyle({
                backgroundColor: 'var(--brand-primary-hover)',
            })
        })

        it('CTA button restores color on mouse leave', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            fireEvent.mouseEnter(cta)
            fireEvent.mouseLeave(cta)
            expect(cta).toHaveStyle({ backgroundColor: 'var(--brand-primary)' })
        })

        // — Footer —
        it('renders footer copyright text', () => {
            render(<LandingPage />)
            expect(
                screen.getByText(/Equitek. All rights reserved/i)
            ).toBeInTheDocument()
        })

        it('renders Privacy Policy link to /privacy', () => {
            render(<LandingPage />)
            expect(screen.getByText('Privacy Policy')).toHaveAttribute(
                'href',
                '/privacy'
            )
        })

        it('renders footer as footer element', () => {
            render(<LandingPage />)
            expect(screen.getByRole('contentinfo')).toBeInTheDocument()
        })

        // — Layout & Style —
        it('applies force-light class on wrapper', () => {
            const { container } = render(<LandingPage />)
            expect(container.firstChild).toHaveClass('force-light')
        })

        it('applies light colorScheme style on wrapper', () => {
            const { container } = render(<LandingPage />)
            expect(container.firstChild).toHaveStyle({ colorScheme: 'light' })
        })

        it('wrapper has min-h-screen and flex flex-col classes', () => {
            const { container } = render(<LandingPage />)
            expect(container.firstChild).toHaveClass('min-h-screen', 'flex', 'flex-col')
        })
    })

    // ❌ NEGATIVE TESTS
    describe('negative', () => {
        it('does not render sidebar', () => {
            render(<LandingPage />)
            expect(screen.queryByText('Convert')).not.toBeInTheDocument()
            expect(screen.queryByText('History')).not.toBeInTheDocument()
        })

        it('does not render upload zone', () => {
            render(<LandingPage />)
            expect(screen.queryByTestId('drop-zone')).not.toBeInTheDocument()
            expect(screen.queryByText('Or drop file here')).not.toBeInTheDocument()
        })

        it('does not render more than 6 feature card headings', () => {
            render(<LandingPage />)
            const headings = screen.getAllByRole('heading', { level: 3 })
            expect(headings.length).toBe(6)
        })

        it('does not render Login or Register more than once', () => {
            render(<LandingPage />)
            expect(screen.getAllByText('Login').length).toBe(1)
            expect(screen.getAllByText('Register').length).toBe(1)
        })

        it('does not render error or loading state on initial render', () => {
            render(<LandingPage />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
            expect(screen.queryByText('Uploading...')).not.toBeInTheDocument()
        })

        it('does not render empty CTA text', () => {
            render(<LandingPage />)
            expect(screen.getByText('Get Started').textContent).not.toBe('')
        })

        it('does not render a form element', () => {
            render(<LandingPage />)
            expect(screen.queryByRole('form')).not.toBeInTheDocument()
        })

        it('does not render file input', () => {
            render(<LandingPage />)
            expect(
                screen.queryByTestId('file-input')
            ).not.toBeInTheDocument()
        })

        it('does not render unknown feature titles', () => {
            render(<LandingPage />)
            expect(screen.queryByText('Unknown Feature')).not.toBeInTheDocument()
            expect(screen.queryByText('Another Feature')).not.toBeInTheDocument()
        })

        it('CTA does not link to wrong path', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            expect(cta).not.toHaveAttribute('href', '/login')
            expect(cta).not.toHaveAttribute('href', '/landing')
            expect(cta).not.toHaveAttribute('href', '/')
        })

        it('Privacy Policy does not link to wrong path', () => {
            render(<LandingPage />)
            const link = screen.getByText('Privacy Policy')
            expect(link).not.toHaveAttribute('href', '/')
            expect(link).not.toHaveAttribute('href', '/convert')
        })

        it('does not apply dark mode styles on wrapper', () => {
            const { container } = render(<LandingPage />)
            expect(container.firstChild).not.toHaveStyle({
                colorScheme: 'dark',
            })
        })
    })
})