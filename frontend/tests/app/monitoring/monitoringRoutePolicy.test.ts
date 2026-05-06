import { describe, expect, it } from 'vitest'
import {
    createMonitoringRouteVisibilityPolicy,
    monitoringRouteVisibilityPolicy,
} from '../../../src/app/monitoring/monitoringRoutePolicy'

describe('monitoring route visibility policy', () => {
    it('treats monitoring routes as system routes regardless of slash or casing', () => {
        expect(monitoringRouteVisibilityPolicy.isSystemRoute('/monitoring/stats/')).toBe(true)
        expect(monitoringRouteVisibilityPolicy.isSystemRoute('Monitoring/STREAM')).toBe(true)
        expect(monitoringRouteVisibilityPolicy.isSystemRoute('/monitoring')).toBe(true)
    })

    it('does not hide routes that only share a partial prefix', () => {
        expect(monitoringRouteVisibilityPolicy.isSystemRoute('/monitoring-health')).toBe(false)
        expect(monitoringRouteVisibilityPolicy.shouldShowRoute('/history/')).toBe(true)
    })

    it('filters visible route rows using the configured policy', () => {
        const visibleRoutes = monitoringRouteVisibilityPolicy.filterVisibleRoutes([
            { route: '/monitoring/stats/', method: 'GET' },
            { route: '/history/', method: 'GET' },
            { route: '/schema/', method: 'POST' },
        ])

        expect(visibleRoutes).toEqual([
            { route: '/history/', method: 'GET' },
            { route: '/schema/', method: 'POST' },
        ])
    })

    it('supports custom hidden prefixes for future route visibility strategies', () => {
        const policy = createMonitoringRouteVisibilityPolicy(['internal', 'admin/tools'])

        expect(policy.isSystemRoute('/internal/jobs/')).toBe(true)
        expect(policy.isSystemRoute('/admin/tools/flush-cache')).toBe(true)
        expect(policy.shouldShowRoute('/admin/users')).toBe(true)
    })

    it('normalizes custom prefixes so callers can pass human-friendly config values', () => {
        const policy = createMonitoringRouteVisibilityPolicy([' /INTERNAL/ ', 'Admin/Tools/'])

        expect(policy.isSystemRoute('/internal/jobs/')).toBe(true)
        expect(policy.isSystemRoute('/admin/tools/flush-cache')).toBe(true)
        expect(policy.shouldShowRoute('/admin/tooling')).toBe(true)
    })
})
