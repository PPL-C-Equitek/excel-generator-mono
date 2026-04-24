import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api', () => ({
    fetchAPI: vi.fn(),
}))

vi.mock('@/lib/auth', () => ({
    getValidAccessToken: vi.fn(),
}))

describe('monitoring service', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('calls live endpoint without auth', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getMonitoringLive } = await import('@/services/monitoring')

        vi.mocked(fetchAPI).mockResolvedValue({ status: 'ok' })
        const result = await getMonitoringLive()

        expect(fetchAPI).toHaveBeenCalledWith('monitoring/live/', { method: 'GET' })
        expect(result).toEqual({ status: 'ok' })
    })

    it('calls access endpoint with bearer token', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringAccess } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-123')
        vi.mocked(fetchAPI).mockResolvedValue({ allowed: true, reason: 'ok' })

        const result = await getMonitoringAccess()

        expect(fetchAPI).toHaveBeenCalledWith('monitoring/access/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer token-123',
            },
        })
        expect(result).toEqual({ allowed: true, reason: 'ok' })
    })

    it('throws when token is missing for protected endpoint', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue(null)

        await expect(getMonitoringReady()).rejects.toThrow(
            'Authentication credentials were not provided.'
        )
        expect(fetchAPI).not.toHaveBeenCalled()
    })

    it('calls stats endpoint with bearer token', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStats } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-456')
        vi.mocked(fetchAPI).mockResolvedValue({
            status: 'ok',
            generated_at: '2026-04-24T10:00:00Z',
            totals: { requests: 1, errors: 0, error_rate: 0 },
            routes: [],
            events: {},
        })

        await getMonitoringStats()

        expect(fetchAPI).toHaveBeenCalledWith('monitoring/stats/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer token-456',
            },
        })
    })
})
