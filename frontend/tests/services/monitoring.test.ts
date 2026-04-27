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

    it('maps readiness payload when endpoint responds with 503 degraded status', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-ready-503')
        const readinessUnavailableError = new Error('Service Unavailable') as Error & { status?: number }
        readinessUnavailableError.status = 503
        vi.mocked(fetchAPI).mockRejectedValueOnce(readinessUnavailableError)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        status: 'degraded',
                        timestamp: '2026-04-26T09:50:00Z',
                        checks: [
                            { name: 'openai_config', status: 'error', latency_ms: 1, is_critical: false },
                        ],
                    }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' },
                    }
                )
            )
        )

        const result = await getMonitoringReady()

        expect(fetchAPI).toHaveBeenCalledWith('monitoring/ready/', {
            method: 'GET',
            headers: {
                Authorization: 'Bearer token-ready-503',
            },
        })
        expect(vi.mocked(fetch)).toHaveBeenCalledWith(
            'http://localhost:8000/monitoring/ready/',
            expect.objectContaining({
                method: 'GET',
                headers: {
                    Authorization: 'Bearer token-ready-503',
                },
            })
        )
        expect(result).toEqual({
            status: 'degraded',
            timestamp: '2026-04-26T09:50:00Z',
            checks: [
                { name: 'openai_config', status: 'error', latency_ms: 1, is_critical: false },
            ],
        })
    })

    it('falls back to default message when readiness fallback returns non-JSON error body', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-ready-non-json')
        const readinessUnavailableError = new Error('Service Unavailable') as Error & { status?: number }
        readinessUnavailableError.status = 503
        vi.mocked(fetchAPI).mockRejectedValueOnce(readinessUnavailableError)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response('not-json-body', {
                    status: 500,
                    headers: { 'Content-Type': 'text/plain' },
                })
            )
        )

        await expect(getMonitoringReady()).rejects.toThrow('Request failed. Please try again.')
    })

    it('uses detail field from readiness fallback error payload', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-ready-detail')
        const readinessUnavailableError = new Error('Service Unavailable') as Error & { status?: number }
        readinessUnavailableError.status = 503
        vi.mocked(fetchAPI).mockRejectedValueOnce(readinessUnavailableError)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({ detail: 'Readiness backend unavailable.' }),
                    {
                        status: 500,
                        headers: { 'Content-Type': 'application/json' },
                    }
                )
            )
        )

        await expect(getMonitoringReady()).rejects.toThrow('Readiness backend unavailable.')
    })

    it('uses message field from readiness fallback error payload', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-ready-message')
        const readinessUnavailableError = new Error('Service Unavailable') as Error & { status?: number }
        readinessUnavailableError.status = 503
        vi.mocked(fetchAPI).mockRejectedValueOnce(readinessUnavailableError)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({ message: 'Readiness check failed.' }),
                    {
                        status: 500,
                        headers: { 'Content-Type': 'application/json' },
                    }
                )
            )
        )

        await expect(getMonitoringReady()).rejects.toThrow('Readiness check failed.')
    })

    it('uses default message when readiness fallback error payload is non-object JSON', async () => {
        const { fetchAPI } = await import('@/lib/api')
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringReady } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-ready-scalar')
        const readinessUnavailableError = new Error('Service Unavailable') as Error & { status?: number }
        readinessUnavailableError.status = 503
        vi.mocked(fetchAPI).mockRejectedValueOnce(readinessUnavailableError)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                new Response(
                    '123',
                    {
                        status: 500,
                        headers: { 'Content-Type': 'application/json' },
                    }
                )
            )
        )

        await expect(getMonitoringReady()).rejects.toThrow('Request failed. Please try again.')
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

    it('uses provided access token for stream without fetching auth token again', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')
        const onPayload = vi.fn()
        const onError = vi.fn()
        vi.mocked(getValidAccessToken).mockResolvedValue('unused-token')

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([
                    `data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:00Z', 1)}\n\n`,
                ])
            )
        )

        const streamHandle = await getMonitoringStatsStream({
            accessToken: 'provided-token',
            onPayload,
            onError,
            intervalSeconds: 2,
        })

        await waitFor(() => {
            expect(onPayload).toHaveBeenCalledTimes(1)
        })
        expect(getValidAccessToken).not.toHaveBeenCalled()
        expect(vi.mocked(fetch)).toHaveBeenCalledWith(
            expect.stringContaining('monitoring/stream/?interval_seconds=2'),
            expect.objectContaining({
                headers: expect.objectContaining({
                    Authorization: 'Bearer provided-token',
                }),
            })
        )

        streamHandle.close()
    })

    it('passes max_events when a valid positive value is provided', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-max-events')

        vi.stubGlobal(
            'fetch',
            vi.fn().mockImplementation(async (url: string) => {
                expect(url).toContain('interval_seconds=3')
                expect(url).toContain('max_events=5')
                return createStreamResponse([`data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:01Z', 1)}\n\n`])
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()
        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
            maxEvents: 5,
            intervalSeconds: 3,
        })

        await waitFor(() => expect(onPayload).toHaveBeenCalledTimes(1))
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )

        streamHandle.close()
    })

    it('omits max_events when no positive value is provided', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-max-events-off')

        const streamURLs: string[] = []
        vi.stubGlobal(
            'fetch',
            vi.fn().mockImplementation(async (url: string) => {
                streamURLs.push(url)
                return createStreamResponse([`data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:01Z', 1)}\n\n`])
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()
        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
            maxEvents: 0,
            intervalSeconds: 0,
        })

        await waitFor(() => expect(onPayload).toHaveBeenCalledTimes(1))
        const streamUrl = streamURLs.at(0)
        expect(streamUrl).toBe('http://localhost:8000/monitoring/stream/?interval_seconds=1')
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )

        streamHandle.close()
    })

    it('omits max_events for negative maxEvents and defaults interval to 1', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-max-events-negative')

        const streamURLs: string[] = []
        vi.stubGlobal(
            'fetch',
            vi.fn().mockImplementation(async (url: string) => {
                streamURLs.push(url)
                return createStreamResponse([`data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:01Z', 1)}\n\n`])
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()
        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
            maxEvents: -2,
            intervalSeconds: -3,
        })

        await waitFor(() => expect(onPayload).toHaveBeenCalledTimes(1))
        const streamUrl = streamURLs.at(0)
        expect(streamUrl).toBe('http://localhost:8000/monitoring/stream/?interval_seconds=1')
        expect(streamURLs.at(0)).not.toContain('max_events=')
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )

        streamHandle.close()
    })

    it('ignores malformed final trailing frame payload after stream closes', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-trailing-malformed')

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([`data: {bad-json`])
            )
        )

        const onPayload = vi.fn()
        const onError = vi.fn()

        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onError).toHaveBeenCalledWith(
                expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
            )
        })

        expect(onPayload).not.toHaveBeenCalled()

        streamHandle.close()
    })

    it('throws when stream response has no readable body', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-empty-body')
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
        )

        await expect(
            getMonitoringStatsStream({
                onPayload: vi.fn(),
                onError: vi.fn(),
                accessToken: 'token-empty-body',
            })
        ).rejects.toThrow('Monitoring stream response has no readable body.')
    })

    it('ignores non-data frames and continues parsing subsequent stream frames', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-no-data')
        const onPayload = vi.fn()
        const onError = vi.fn()

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([
                    ': keep-alive\n\n',
                    `data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:00Z', 1)}\n\n`,
                ])
            )
        )

        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onPayload).toHaveBeenCalledTimes(1)
        })
        expect(onPayload).toHaveBeenCalledWith(
            expect.objectContaining({
                generated_at: '2026-04-24T10:00:00Z',
            })
        )
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )

        streamHandle.close()
    })

    it('parses final partial stream frame from trailing payload after stream closes', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-trailing')
        const onPayload = vi.fn()
        const onError = vi.fn()

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue(
                createStreamResponse([`data: ${createMonitoringStatsStreamPayload('2026-04-24T10:00:09Z', 7)}`])
            )
        )

        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onPayload).toHaveBeenCalledTimes(1)
        })
        expect(onPayload).toHaveBeenCalledWith(
            expect.objectContaining({
                generated_at: '2026-04-24T10:00:09Z',
            })
        )
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream closed unexpectedly.' })
        )

        streamHandle.close()
    })

    it('does not emit parse errors when the stream is manually closed before data is emitted', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-close')

        let signal: AbortSignal | undefined
        const cancel = vi.fn().mockResolvedValue(undefined)
        const read = vi.fn(() =>
            new Promise<ReadableStreamReadResult<Uint8Array>>((resolve) => {
                if (signal?.aborted) {
                    resolve({ done: true, value: undefined })
                    return
                }

                signal?.addEventListener(
                    'abort',
                    () => {
                        resolve({ done: true, value: undefined })
                    },
                    { once: true }
                )
            })
        )

        vi.stubGlobal(
            'fetch',
            vi.fn().mockImplementation((_url, init) => {
                signal = init?.signal as AbortSignal
                return Promise.resolve({
                    ok: true,
                    body: {
                        getReader: () => ({ read, cancel }),
                    },
                })
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()
        const streamHandle = await getMonitoringStatsStream({
            onPayload,
            onError,
        })

        streamHandle.close()
        streamHandle.close()

        await waitFor(() => {
            expect(onPayload).not.toHaveBeenCalled()
            expect(onError).not.toHaveBeenCalled()
            expect(cancel).toHaveBeenCalledTimes(1)
        })
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

    it('falls back to generic stream parsing error when reader fails with non-Error rejection', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-non-error')

        const read = vi.fn().mockRejectedValue('bad stream payload')
        const cancel = vi.fn().mockResolvedValue(undefined)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                body: {
                    getReader: () => ({ read, cancel }),
                },
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()

        await getMonitoringStatsStream({
            accessToken: 'token-non-error',
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onError).toHaveBeenCalledTimes(1)
        })
        expect(onPayload).not.toHaveBeenCalled()
        expect(onError).toHaveBeenCalledWith(
            expect.objectContaining({ message: 'Monitoring stream parse failed.' })
        )
    })

    it('ignores reader AbortError rejections from stream parser', async () => {
        const { getValidAccessToken } = await import('@/lib/auth')
        const { getMonitoringStatsStream } = await import('@/services/monitoring')

        vi.mocked(getValidAccessToken).mockResolvedValue('token-abort-error')
        const abortError = new DOMException('Stream closed', 'AbortError')
        const read = vi.fn().mockRejectedValue(abortError)
        const cancel = vi.fn().mockResolvedValue(undefined)

        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                body: {
                    getReader: () => ({ read, cancel }),
                },
            })
        )

        const onPayload = vi.fn()
        const onError = vi.fn()

        await getMonitoringStatsStream({
            accessToken: 'token-abort-error',
            onPayload,
            onError,
        })

        await waitFor(() => {
            expect(onPayload).not.toHaveBeenCalled()
            expect(onError).not.toHaveBeenCalled()
            expect(cancel).toHaveBeenCalledTimes(1)
        })
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
