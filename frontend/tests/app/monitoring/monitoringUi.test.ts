import { describe, expect, it } from 'vitest'
import {
    clamp,
    formatPercent,
    formatReadinessCheckName,
    formatStatusLabel,
    formatTimeLabel,
    formatTimestamp,
    resolveAccessMessage,
    statusBadgeClass,
} from '../../../src/app/monitoring/monitoringUi'

describe('monitoringUi helpers', () => {
    it('returns raw value for invalid timestamp and time label input', () => {
        expect(formatTimestamp('invalid-timestamp')).toBe('invalid-timestamp')
        expect(formatTimeLabel('invalid-time')).toBe('invalid-time')
    })

    it('formats finite and non-finite percentages', () => {
        expect(formatPercent(0.1234)).toBe('12.34%')
        expect(formatPercent(Number.POSITIVE_INFINITY)).toBe('0.00%')
    })

    it('maps status badge classes including degraded branch', () => {
        expect(statusBadgeClass('ok')).toContain('text-blue-700')
        expect(statusBadgeClass('degraded')).toContain('border-red-300')
        expect(statusBadgeClass('error')).toContain('border-red-400')
        expect(statusBadgeClass('unknown')).toContain('border-gray-300')
    })

    it('normalizes status labels and readiness check names', () => {
        expect(formatStatusLabel('ok')).toBe('OK')
        expect(formatStatusLabel('error')).toBe('Error')
        expect(formatStatusLabel('warning')).toBe('warning')

        expect(formatReadinessCheckName('database')).toBe('Database')
        expect(formatReadinessCheckName(' storage ')).toBe('Storage')
        expect(formatReadinessCheckName('openai_config')).toBe('LLM Config')
        expect(formatReadinessCheckName('queue')).toBe('queue')
    })

    it('resolves known and unknown access reasons and clamps numbers', () => {
        expect(resolveAccessMessage('ok')).toBe('Monitoring access granted.')
        expect(resolveAccessMessage('custom_reason')).toBe('Access status: custom_reason')
        expect(clamp(15, 0, 10)).toBe(10)
        expect(clamp(-2, 0, 10)).toBe(0)
    })
})

