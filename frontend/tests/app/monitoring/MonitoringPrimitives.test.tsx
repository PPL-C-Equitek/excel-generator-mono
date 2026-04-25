import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
    GaugeMeter,
    MetricCard,
    StatusBadge,
} from '../../../src/app/monitoring/components/primitives/MonitoringPrimitives'

describe('MonitoringPrimitives', () => {
    it('renders status badge with fallback label from status', () => {
        render(<StatusBadge status="ok" />)

        expect(screen.getByText('ok')).toBeInTheDocument()
    })

    it('renders metric card subtitle only when provided', () => {
        const { rerender } = render(
            <MetricCard title="Requests" value="10" subtitle="Current window" />
        )

        expect(screen.getByText('Current window')).toBeInTheDocument()

        rerender(<MetricCard title="Requests" value="10" />)
        expect(screen.queryByText('Current window')).not.toBeInTheDocument()
    })

    it('renders gauge meter with progress arc and caption', () => {
        const { container } = render(
            <GaugeMeter
                ariaLabel="Error rate meter"
                label="Error Rate Meter"
                valueText="5.00%"
                caption="Window 60s"
                progressLength={125.6}
                strokeColor="#b91c1c"
                valueClassName="text-red-700"
            />
        )

        expect(screen.getByLabelText('Error rate meter')).toBeInTheDocument()
        expect(screen.getByText('Window 60s')).toBeInTheDocument()
        expect(container.querySelector('path[stroke-dasharray="125.6 251.2"]')).not.toBeNull()
    })
})
