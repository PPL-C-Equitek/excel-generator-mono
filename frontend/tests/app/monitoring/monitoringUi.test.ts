import { describe, expect, it } from 'vitest'
import {
    clamp,
    formatPercent,
    formatTimeLabel,
    formatTimestamp,
    resolveAccessMessage,
    statusBadgeClass,
} from '../../../src/app/monitoring/monitoringUi'

describe('monitoringUi helpers', () => {
    it('returns original value for invalid timestamp strings', () => {
        expect(formatTimestamp('invalid-date')).toBe('invalid-date')
        expect(formatTimeLabel('invalid-time')).toBe('invalid-time')
    })

    it('formats percentages and falls back for non-finite values', () => {
        expect(formatPercent(0.125)).toBe('12.50%')
        expect(formatPercent(Number.NaN)).toBe('0.00%')
        expect(formatPercent(Number.POSITIVE_INFINITY)).toBe('0.00%')
    })

    it('maps status badges to expected classes', () => {
        expect(statusBadgeClass('ok')).toContain('text-blue-700')
        expect(statusBadgeClass('degraded')).toContain('text-red-700')
        expect(statusBadgeClass('down')).toContain('border-red-400')
        expect(statusBadgeClass('exception')).toContain('border-red-400')
        expect(statusBadgeClass('error')).toContain('border-red-400')
        expect(statusBadgeClass('custom')).toContain('text-gray-700')
    })

    it('resolves access messages with fallback', () => {
        expect(resolveAccessMessage('ok')).toBe('Monitoring access granted.')
        expect(resolveAccessMessage('custom_reason')).toBe('Access status: custom_reason')
    })

    it('clamps values into min/max boundaries', () => {
        expect(clamp(10, 0, 5)).toBe(5)
        expect(clamp(-1, 0, 5)).toBe(0)
        expect(clamp(3, 0, 5)).toBe(3)
    })
})
