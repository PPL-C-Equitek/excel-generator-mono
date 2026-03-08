import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import LandingPage from '../../../src/app/landing/LandingPage'

describe('LandingPage', () => {
    // Positive tests
    describe('positive', () => {
        it('renders Navbar with brand name', () => {
            render(<LandingPage />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('renders HeroSection', () => {
            render(<LandingPage />)
            expect(screen.getByTestId('hero-section')).toBeInTheDocument()
        })

        it('renders Why Use Our Service heading', () => {
            render(<LandingPage />)
            expect(screen.getByText('Why Use Our Service?')).toBeInTheDocument()
        })

        it('renders all 6 feature cards', () => {
            render(<LandingPage />)
            const features = [
                'Advanced AI Transformation',
                'Instance Excel Mapping',
                'Verified Logic',
                'Full Traceability',
                'Consultant-Grade Standards',
                'Seamless Automation',
            ]
            features.forEach((feature) => {
                expect(screen.getByText(feature)).toBeInTheDocument()
            })
        })

        it('renders CTA button linking to /convert', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            expect(cta).toBeInTheDocument()
            expect(cta).toHaveAttribute('href', '/convert')
        })

        it('renders footer copyright text', () => {
            render(<LandingPage />)
            expect(
                screen.getByText(/Equitek. All rights reserved/i)
            ).toBeInTheDocument()
        })

        it('renders Privacy Policy link', () => {
            render(<LandingPage />)
            expect(screen.getByText('Privacy Policy')).toHaveAttribute('href', '/privacy')
        })
    })

    // Negative tests
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

        it('does not render more than 6 feature cards', () => {
            render(<LandingPage />)
            const headings = screen.getAllByRole('heading', { level: 3 })
            expect(headings.length).toBe(6)
        })

        it('does not render Login or Register in footer', () => {
            render(<LandingPage />)
            // Login & Register hanya boleh ada di Navbar
            expect(screen.getAllByText('Login').length).toBe(1)
            expect(screen.getAllByText('Register').length).toBe(1)
        })

        it('does not render error or loading state on initial render', () => {
            render(<LandingPage />)
            expect(screen.queryByRole('alert')).not.toBeInTheDocument()
            expect(screen.queryByText('Uploading...')).not.toBeInTheDocument()
        })

        it('does not render empty CTA section', () => {
            render(<LandingPage />)
            const cta = screen.getByText('Get Started')
            expect(cta.textContent).not.toBe('')
        })
    })
})