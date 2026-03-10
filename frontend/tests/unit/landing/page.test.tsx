import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Page from '../../../src/app/landing/page'

vi.mock('../../../src/app/landing/LandingPage', () => ({
    default: () => <div data-testid="landing-page-mock">LandingPage</div>,
}))

describe('Landing Page (page.tsx)', () => {
    it('renders without crashing', () => {
        render(<Page />)
        expect(screen.getByTestId('landing-page-mock')).toBeInTheDocument()
    })

    it('renders LandingPage component', () => {
        render(<Page />)
        expect(screen.getByText('LandingPage')).toBeInTheDocument()
    })
})