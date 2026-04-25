import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { waitFor } from '@testing-library/react'

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

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    function createStreamResponse(chunks: string[]): Response {
        const encoder = new TextEncoder()
        const chunksCopy = [...chunks]

        const stream = new ReadableStream<Uint8Array>({
            pull(controller) {
                if (chunksCopy.length === 0) {
                    controller.close()
                    return
                }

                const chunk = chunksCopy.shift()
                if (chunk === undefined) {
                    controller.close()
                    return
                }

                controller.enqueue(encoder.encode(chunk))
            },
        })

        return new Response(stream, {
            status: 200,
            headers: { 'Content-Type': 'text/event-stream' },
        })
    }

    function createMonitoringStatsStreamPayload(
        generatedAt: string,
        totalRequests: number,
    ) {
        return JSON.stringify({
            status: 'ok',
            generated_at: generatedAt,
            totals: { requests: totalRequests, errors: 0, error_rate: 0 },
            routes: [],
            events: {},
            timeseries: {
                window_seconds: 20,
                bucket_seconds: 10,
                points: [],
            },
        })
    }

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

    it('reuses caller-provided token for all protected endpoints without fetching again', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const {
            getMonitoringAccess,
            getMonitoringReady,
            getMonitoringStats,
        } = await import('@/services/monitoring')

        vi.mocked(fetchAPI).mockResolvedValue({})

        const accessPromise = getMonitoringAccess('shared-token')
        const readyPromise = getMonitoringReady('shared-token')
        const statsPromise = getMonitoringStats('shared-token')

        await Promise.all([accessPromise, readyPromise, statsPromise])

        expect(vi.mocked(getValidAccessToken)).not.toHaveBeenCalled()
        expect(fetchAPI).toHaveBeenCalledWith('monitoring/access/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer shared-token',
            },
        })
        expect(fetchAPI).toHaveBeenCalledWith('monitoring/ready/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer shared-token',
            },
        })
        expect(fetchAPI).toHaveBeenCalledWith('monitoring/stats/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer shared-token',
            },
        })
        expect(fetchAPI).toHaveBeenCalledTimes(3)
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

    it('reuses a single token for one snapshot request', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringAuthenticatedSnapshot } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('shared-token')
        vi.mocked(fetchAPI)
            .mockResolvedValueOnce({
                access: { allowed: true, reason: 'ok' },
                ready: {
                    status: 'ok',
                    timestamp: '2026-04-24T10:00:00Z',
                    checks: [
                        { name: 'database', status: 'ok', latency_ms: 1, is_critical: true },
                    ],
                },
                stats: {
                    status: 'ok',
                    generated_at: '2026-04-24T10:00:00Z',
                    totals: { requests: 1, errors: 0, error_rate: 0 },
                    routes: [],
                    events: {},
                },
            })

        const result = await getMonitoringAuthenticatedSnapshot()

        expect(getValidAccessToken).toHaveBeenCalledTimes(1)
        expect(fetchAPI).toHaveBeenNthCalledWith(1, 'monitoring/snapshot/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer shared-token',
            },
        })
        expect(fetchAPI).toHaveBeenCalledTimes(1)
        expect(result.accessDecision).toEqual({ allowed: true, reason: 'ok' })
        expect(result.readyPayload?.status).toBe('ok')
        expect(result.statsPayload?.status).toBe('ok')
    })

    it('stops snapshot flow after access denied snapshot payload', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringAuthenticatedSnapshot } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('shared-token')
        vi.mocked(fetchAPI).mockResolvedValueOnce({
            access: { allowed: false, reason: 'no_account' },
            ready: null,
            stats: null,
        })

        const result = await getMonitoringAuthenticatedSnapshot()

        expect(getValidAccessToken).toHaveBeenCalledTimes(1)
        expect(fetchAPI).toHaveBeenCalledTimes(1)
        expect(fetchAPI).toHaveBeenNthCalledWith(1, 'monitoring/snapshot/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer shared-token',
            },
        })
        expect(result).toEqual({
            accessDecision: { allowed: false, reason: 'no_account' },
            readyPayload: null,
            statsPayload: null,
        })
    })

    it('streams monitoring stats payloads and parses chunked SSE data', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-abc')
        const onPayload = vi.fn()
        const onError = vi.fn()

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([
                    `data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:00Z', 1)}\n\n`,
                    `: keep-alive\n`,
                    `data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:01Z', 2)}\n\n`,
                ])
            )
        )

        const streamHandle = await getMonitoringStatsStream({
            accessToken: 'token-abc',
            onPayload,
            onError,
            intervalSeconds: 2,
        })

        await waitFor(() => {
            expect(onPayload).toHaveBeenCalledTimes(2)
        })

        expect(onError).toHaveBeenCalledTimes(1)
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )
        expect(onPayload).toHaveBeenNthCalledWith(1, {
            status: 'ok',
            generated_at: '2026-04-24T10:00:00Z',
            totals: { requests: 1, errors: 0, error_rate: 0 },
            routes: [],
            events: {},
            timeseries: {
                window_seconds: 20,
                bucket_seconds: 10,
                points: [],
            },
        })
        expect(onPayload).toHaveBeenNthCalledWith(2, {
            status: 'ok',
            generated_at: '2026-04-24T10:00:01Z',
            totals: { requests: 2, errors: 0, error_rate: 0 },
            routes: [],
            events: {},
            timeseries: {
                window_seconds: 20,
                bucket_seconds: 10,
                points: [],
            },
        })

        streamHandle.close()
    })

    it('retries stream gracefully when SSE payload is malformed', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-err')
        const onPayload = vi.fn()
        const onError = vi.fn()

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([
                    'data: {bad-json}\n\n',
                ])
            )
        )

        await getMonitoringStatsStream({
            accessToken: 'token-err',
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onError).toHaveBeenCalledTimes(1)
        })
        expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error)
        expect(onPayload).not.toHaveBeenCalled()
    })

    it('throws when streaming endpoint is unavailable', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-down')
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response(null, {
                    status: 503,
                })
            )
        )

        await expect(
            getMonitoringStatsStream({ accessToken: 'token-down', onPayload: vi.fn() })
        ).rejects.toThrow('Monitoring stream is unavailable.')
    })
})
