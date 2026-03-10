import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Home from '@/app/page'

vi.mock('@/app/landing/LandingPage', () => ({
    default: () => <div data-testid="landing-page-mock">LandingPage</div>,
}))

describe('Home page', () => {
    it('renders landing page at root route', () => {
        render(<Home />)
        expect(screen.getByTestId('landing-page-mock')).toBeInTheDocument()
        expect(screen.getByText('LandingPage')).toBeInTheDocument()
    })
})
