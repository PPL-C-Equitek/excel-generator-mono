import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
    GaugeMeter,
    MetricCard,
    StatusBadge,
} from '../../../../../src/app/monitoring/components/primitives/MonitoringPrimitives'

describe('MonitoringPrimitives', () => {
    it('renders status badge with fallback label when label prop is omitted', () => {
        render(<StatusBadge status="ok" />)
        expect(screen.getByText('ok')).toBeInTheDocument()
    })

    it('renders metric card without subtitle', () => {
        render(
            <MetricCard title="Requests" value="12" />
        )
        expect(screen.getByText('Requests')).toBeInTheDocument()
        expect(screen.queryByText(/^subtitle/i)).not.toBeInTheDocument()
    })

    it('renders gauge meter with aria label and caption', () => {
        render(
            <GaugeMeter
                ariaLabel="Error rate meter"
                label="Error Rate Meter"
                valueText="5.00%"
                caption="Window 60s"
                progressLength={12.56}
                strokeColor="#b91c1c"
                valueClassName="text-red-700"
            />
        )
        expect(screen.getByLabelText('Error rate meter')).toBeInTheDocument()
        expect(screen.getByText('Window 60s')).toBeInTheDocument()
    })
})

