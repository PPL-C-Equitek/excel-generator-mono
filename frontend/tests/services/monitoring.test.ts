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
        expect(result).toEqual({ status: 'ok', timestamp: '' })
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

    it('normalizes malformed stats payload from API', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStats } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-789')
        vi.mocked(fetchAPI).mockResolvedValue({
            status: 123,
            totals: {
                requests: 'abc',
                errors: 2,
            },
            routes: [{ route: null, method: 'GET' }],
            events: {
                login: {
                    success: 'x',
                },
            },
            timeseries: {
                window_seconds: 60,
                bucket_seconds: '10',
                points: [{ timestamp: 1, requests: 3 }],
            },
        })

        const payload = await getMonitoringStats()

        expect(payload).toEqual({
            status: 'unknown',
            generated_at: '',
            totals: {
                requests: 0,
                errors: 2,
                error_rate: 0,
            },
            routes: [
                {
                    route: 'unknown',
                    method: 'GET',
                    total_requests: 0,
                    total_errors: 0,
                    error_rate: 0,
                    avg_latency_ms: 0,
                    max_latency_ms: 0,
                },
            ],
            events: {
                login: {
                    success: 0,
                },
            },
            timeseries: {
                window_seconds: 60,
                bucket_seconds: 0,
                points: [
                    {
                        timestamp: '',
                        requests: 3,
                        errors: 0,
                        error_rate: 0,
                        avg_latency_ms: 0,
                    },
                ],
            },
        })
    })
})
