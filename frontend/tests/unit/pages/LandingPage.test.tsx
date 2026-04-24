import { render, screen, fireEvent, within, act } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import LandingPage from '../../../src/app/landing/LandingPage'
import { LANDING_FEATURES, LANDING_NAV_LINKS, LANDING_HERO_CONFIG } from '../../../src/constants/landing'

const mockHasValidSession = vi.fn<() => Promise<boolean>>()

vi.mock('@/components/LogoutButton', () => ({
    default: () => <button type="button">Logout</button>,
}))

vi.mock('@/lib/auth', async () => {
    const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth')

    return {
        ...actual,
        hasValidSession: () => mockHasValidSession(),
    }
})

/**
 * LandingPage Integration Tests
 * 
 * Tests verify that SOLID principles are correctly applied:
 * 
 * SRP (Single Responsibility Principle):
 *  - LandingPage assembles sections, doesn't contain business data
 *  - Data lives in constants/landing.ts
 * 
 * DIP (Dependency Inversion Principle):
 *  - Components accept data via props (NavLink[], Feature[], etc.)
 *  - Not hardcoded, making components reusable and testable
 * 
 * OCP (Open/Closed Principle):
 *  - Easy to extend: Add features to LANDING_FEATURES, they auto-render
 *  - Easy to modify: Change brand name, hero text in constants without touching component logic
 * 
 * ISP (Interface Segregation Principle):
 *  - Each component uses minimal interface contracts (Feature, NavLink, etc.)
 *  - Not coupled to unnecessary data
 */
describe('LandingPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
        mockHasValidSession.mockResolvedValue(false)
    })

    // POSITIVE TESTS
    describe('positive', () => {
        // — Navbar —
        it('renders Navbar with brand name', () => {
            render(<LandingPage />)
            expect(screen.getByText('EQUITEK')).toBeInTheDocument()
        })

        it('renders all navigation links from LANDING_NAV_LINKS constant', () => {
            render(<LandingPage />)
            LANDING_NAV_LINKS.forEach((link) => {
                expect(screen.getByText(link.label)).toBeInTheDocument()
                expect(screen.getByText(link.label)).toHaveAttribute('href', link.href)
            })
        })

        it('renders correct number of nav links', () => {
            render(<LandingPage />)
            const navbar = screen.getByTestId('navbar')
            const navLinks = within(navbar).getAllByRole('link')
            expect(navLinks).toHaveLength(LANDING_NAV_LINKS.length + 1)
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

        it('renders hero heading from LANDING_HERO_CONFIG', () => {
            render(<LandingPage />)
            expect(screen.getByText(LANDING_HERO_CONFIG.heading)).toBeInTheDocument()
        })

        it('renders hero subtitle from LANDING_HERO_CONFIG', () => {
            render(<LandingPage />)
            expect(screen.getByText(LANDING_HERO_CONFIG.subtitle)).toBeInTheDocument()
        })

        // — Features —
        it('renders Why Use Our Service heading', () => {
            render(<LandingPage />)
            expect(screen.getByText('Why Use Our Service?')).toBeInTheDocument()
        })

        it('renders all feature titles from LANDING_FEATURES constant (OCP: extensible)', () => {
            render(<LandingPage />)
            LANDING_FEATURES.forEach((feature) => {
                expect(screen.getByText(feature.title)).toBeInTheDocument()
            })
        })

        it('renders all feature descriptions from LANDING_FEATURES constant', () => {
            render(<LandingPage />)
            LANDING_FEATURES.forEach((feature) => {
                expect(screen.getByText(feature.desc)).toBeInTheDocument()
            })
        })

        it('renders correct number of feature cards (SRP + DIP: data-driven)', () => {
            render(<LandingPage />)
            const featureHeadings = screen.getAllByRole('heading', { level: 3 })
            expect(featureHeadings).toHaveLength(LANDING_FEATURES.length)
        })

        it('renders features in a grid container', () => {
            render(<LandingPage />)
            const grid = screen.getByTestId('features-grid')
            expect(grid).toBeInTheDocument()
            expect(grid).toHaveClass('grid')
            expect(grid).toHaveClass('grid-cols-1')

            const featureCards = within(grid).getAllByRole('heading', { level: 3 })
            expect(featureCards).toHaveLength(LANDING_FEATURES.length)
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

        it('hides Login and Register links when user is already logged in', async () => {
            window.localStorage.setItem('access_token', 'existing-token')
            window.localStorage.setItem('refresh_token', 'refresh-token')
            mockHasValidSession.mockResolvedValue(true)

            render(<LandingPage />)

            await act(async () => {
                await Promise.resolve()
            })

            expect(screen.queryByText('Login')).not.toBeInTheDocument()
            expect(screen.queryByText('Register')).not.toBeInTheDocument()
            expect(screen.getByText('Convert')).toBeInTheDocument()
            expect(screen.getByText('Schema')).toBeInTheDocument()
            expect(screen.getByText('History')).toBeInTheDocument()
            expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument()
        })
    })

    // NEGATIVE TESTS
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

        it('does not render more feature cards than in LANDING_FEATURES', () => {
            render(<LandingPage />)
            const headings = screen.getAllByRole('heading', { level: 3 })
            expect(headings.length).toBe(LANDING_FEATURES.length)
        })

        it('does not render nav links more than once', () => {
            render(<LandingPage />)
            LANDING_NAV_LINKS.forEach((link) => {
                expect(screen.getAllByText(link.label)).toHaveLength(1)
            })
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
