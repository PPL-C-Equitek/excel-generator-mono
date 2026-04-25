import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GaugeMeter, MetricCard, StatusBadge } from '../../../src/app/monitoring/components/primitives/MonitoringPrimitives'

describe('MonitoringPrimitives', () => {
    it('renders status badge with explicit label and extra class', () => {
        render(<StatusBadge status="ok" label="All Good" className="border-red-500" />)

        expect(screen.getByText('All Good')).toBeInTheDocument()
        expect(screen.getByText('All Good').className).toContain('border-red-500')
        expect(screen.getByText('All Good').className).toContain('border-blue-200')
    })

    it('falls back to status when label is omitted', () => {
        render(<StatusBadge status="down" />)

        expect(screen.getByText('down')).toBeInTheDocument()
    })

    it('renders metric card with subtitle and custom children', () => {
        render(
            <MetricCard
                title="Throughput"
                value="100 req/s"
                subtitle="live"
                valueClassName="text-blue-700"
            >
                <span>child</span>
            </MetricCard>
        )

        expect(screen.getByText('Throughput')).toBeInTheDocument()
        expect(screen.getByText('100 req/s')).toBeInTheDocument()
        expect(screen.getByText('live')).toBeInTheDocument()
        expect(screen.getByText('child')).toBeInTheDocument()
    })

    it('renders metric card without subtitle when not provided', () => {
        render(
            <MetricCard
                title="Requests"
                value="500"
            />
        )

        expect(screen.getByText('Requests')).toBeInTheDocument()
        expect(screen.getByText('500')).toBeInTheDocument()
        expect(screen.queryByText('live')).not.toBeInTheDocument()
    })

    it('renders gauge meter with expected labels and progress style', () => {
        render(
            <GaugeMeter
                ariaLabel="Error rate meter"
                label="Error Rate"
                valueText="12.00%"
                caption="Window 60s"
                progressLength={120}
                strokeColor="#2563eb"
                valueClassName="text-blue-600"
            />
        )

        expect(screen.getByText('Error Rate')).toBeInTheDocument()
        expect(screen.getByText('12.00%')).toBeInTheDocument()
        expect(screen.getByText('Window 60s')).toBeInTheDocument()
    })
})
