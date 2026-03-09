import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import FeatureCard from '../../../src/components/FeatureCard'
import type { Feature } from '../../../src/constants/landing'

/**
 * FeatureCard Component Tests
 * 
 * SOLID principles demonstrated:
 * - SRP: Component has single responsibility - render a feature card
 * - ISP: Accepts Feature interface (only title, desc, icon it needs)
 * - OCP: Easy to extend - accepts custom icon prop
 * - DIP: Data injected via props, not hardcoded
 */
describe('FeatureCard', () => {
    const defaultProps: Feature = {
        title: 'Advanced AI Transformation',
        desc: 'Leverage advanced LLMs to accurately interpret unstructured data',
    }

    // Positive tests
    describe('positive', () => {
        it('renders title correctly', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.getByText('Advanced AI Transformation')).toBeInTheDocument()
        })

        it('renders description correctly', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(
                screen.getByText(/Leverage advanced LLMs/i)
            ).toBeInTheDocument()
        })

        it('renders custom icon when provided', () => {
            const propsWithIcon: Feature = {
                ...defaultProps,
                icon: <span>🤖</span>
            }
            render(<FeatureCard {...propsWithIcon} />)
            expect(screen.getByText('🤖')).toBeInTheDocument()
        })

        it('renders fallback icon when no icon provided', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.getByText('▪')).toBeInTheDocument()
        })

        it('renders title as heading element', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument()
        })

        it('accepts Feature interface contract (ISP)', () => {
            const customFeature: Feature = {
                title: 'Custom Feature',
                desc: 'Custom description for testing',
            }
            render(<FeatureCard {...customFeature} />)
            expect(screen.getByText('Custom Feature')).toBeInTheDocument()
            expect(screen.getByText('Custom description for testing')).toBeInTheDocument()
        })
    })

    // Negative tests
    describe('negative', () => {
        it('does not render empty title', () => {
            render(<FeatureCard {...defaultProps} />)
            const heading = screen.getByRole('heading', { level: 3 })
            expect(heading.textContent).not.toBe('')
        })

        it('does not render other feature titles', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.queryByText('Full Traceability')).not.toBeInTheDocument()
            expect(screen.queryByText('Verified Logic')).not.toBeInTheDocument()
        })

        it('does not render a button', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.queryByRole('button')).not.toBeInTheDocument()
        })

        it('does not render a link', () => {
            render(<FeatureCard {...defaultProps} />)
            expect(screen.queryByRole('link')).not.toBeInTheDocument()
        })
    })
})