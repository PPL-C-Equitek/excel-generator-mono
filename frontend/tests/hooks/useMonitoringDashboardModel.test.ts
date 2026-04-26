import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.mock('@/lib/auth', () => ({
    getValidAccessToken: vi.fn(),
}))
import { getValidAccessToken } from '@/lib/auth'
import type {
    MonitoringAccessDecision,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
} from '../../src/services/monitoring'
import {
    getIsPageVisible,
    useMonitoringDashboardModel,
    type MonitoringDashboardService,
} from '../../src/app/monitoring/useMonitoringDashboardModel'

function createMonitoringService(
    overrides: Partial<MonitoringDashboardService> = {}
): MonitoringDashboardService {
    const defaultLive: MonitoringLivePayload = {
        status: 'ok',
        timestamp: '2026-04-24T10:00:00Z',
    }
    const defaultAccess: MonitoringAccessDecision = {
        allowed: true,
        reason: 'ok',
    }
    const defaultReady: MonitoringReadyPayload = {
        status: 'ok',
        timestamp: '2026-04-24T10:00:01Z',
        checks: [{ name: 'database', status: 'ok', latency_ms: 3, is_critical: true }],
    }
    const defaultStats: MonitoringStatsPayload = {
        status: 'ok',
        generated_at: '2026-04-24T10:00:02Z',
        totals: { requests: 4, errors: 1, error_rate: 0.25 },
        routes: [
            {
                route: 'history/',
                method: 'GET',
                total_requests: 4,
                total_errors: 1,
                error_rate: 0.25,
                avg_latency_ms: 75,
                max_latency_ms: 120,
            },
        ],
        events: {
            'auth.login': {
                success: 5,
                client_error: 1,
            },
        },
        timeseries: {
            window_seconds: 20,
            bucket_seconds: 10,
            points: [
                {
                    timestamp: '2026-04-24T10:00:00Z',
                    requests: 2,
                    errors: 1,
                    error_rate: 0.5,
                    avg_latency_ms: 100,
                },
                {
                    timestamp: '2026-04-24T10:00:10Z',
                    requests: 2,
                    errors: 0,
                    error_rate: 0,
                    avg_latency_ms: 200,
                },
            ],
        },
    }

    return {
        getMonitoringLive: vi.fn().mockResolvedValue(defaultLive),
        getMonitoringAccess: vi.fn().mockResolvedValue(defaultAccess),
        getMonitoringReady: vi.fn().mockResolvedValue(defaultReady),
        getMonitoringStats: vi.fn().mockResolvedValue(defaultStats),
        ...overrides,
    }
}

function createDeferred<T>() {
    let resolve!: (value: T | PromiseLike<T>) => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<T>((nextResolve, nextReject) => {
        resolve = nextResolve
        reject = nextReject
    })
    return {
        promise,
        resolve,
        reject,
    }
}

function makeStreamStatsPayload(): MonitoringStatsPayload {
    return {
        status: 'ok',
        generated_at: '2026-04-24T10:00:05Z',
        totals: { requests: 200, errors: 2, error_rate: 0.01 },
        routes: [
            {
                route: '/monitoring/stream/',
                method: 'GET',
                total_requests: 100,
                total_errors: 1,
                error_rate: 0.01,
                avg_latency_ms: 12,
                max_latency_ms: 25,
            },
        ],
        events: {
            'monitoring.stream': {
                ok: 2,
            },
        },
        timeseries: {
            window_seconds: 10,
            bucket_seconds: 5,
            points: [
                {
                    timestamp: '2026-04-24T10:00:03Z',
                    requests: 5,
                    errors: 0,
                    error_rate: 0,
                    avg_latency_ms: 12,
                },
            ],
        },
    }
}

describe('useMonitoringDashboardModel', () => {
    beforeEach(() => {
        vi.mocked(getValidAccessToken).mockResolvedValue('test-access-token')
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('skips ready and stats calls when access is denied', async () => {
        const service = createMonitoringService({
            getMonitoringAccess: vi.fn().mockResolvedValue({
                allowed: false,
                reason: 'no_account',
            }),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.accessDecision).toEqual({
            allowed: false,
            reason: 'no_account',
        })
        expect(result.current.readyPayload).toBeNull()
        expect(result.current.statsPayload).toBeNull()
        expect(service.getMonitoringReady).not.toHaveBeenCalled()
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
    })

    it('reuses one auth token for non-snapshot access/ready/stats flow', async () => {
        const service = createMonitoringService()

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(vi.mocked(getValidAccessToken)).toHaveBeenCalledTimes(1)
        expect(service.getMonitoringAccess).toHaveBeenCalledWith('test-access-token')
        expect(service.getMonitoringReady).toHaveBeenCalledWith('test-access-token')
        expect(service.getMonitoringStats).toHaveBeenCalledWith('test-access-token')
    })

    it('fails when auth token is unavailable for non-snapshot monitoring flow', async () => {
        vi.mocked(getValidAccessToken).mockResolvedValueOnce(null)
        const service = createMonitoringService({
            getMonitoringAccess: vi.fn(),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.errorMessage).toBe('Authentication credentials were not provided.')
        expect(service.getMonitoringAccess).not.toHaveBeenCalled()
        expect(service.getMonitoringReady).not.toHaveBeenCalled()
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
    })

    it('polls monitoring endpoints on the configured interval', async () => {
        const service = createMonitoringService()

        renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 20,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalled()
        })

        await waitFor(() => {
            expect(service.getMonitoringLive.mock.calls.length).toBeGreaterThanOrEqual(2)
            expect(service.getMonitoringAccess.mock.calls.length).toBeGreaterThanOrEqual(2)
        })
    })

    it('computes derived metrics from realtime timeseries and readiness data', async () => {
        const service = createMonitoringService({
            getMonitoringReady: vi.fn().mockResolvedValue({
                status: 'degraded',
                timestamp: '2026-04-24T10:00:01Z',
                checks: [
                    { name: 'database', status: 'ok', latency_ms: 3, is_critical: true },
                    { name: 'openai', status: 'error', latency_ms: 7, is_critical: false },
                ],
            }),
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 100, errors: 20, error_rate: 0.2 },
                routes: [],
                events: {
                    event_b: { success: 3 },
                    event_a: { success: 5 },
                },
                timeseries: {
                    window_seconds: 20,
                    bucket_seconds: 10,
                    points: [
                        {
                            timestamp: '2026-04-24T10:00:00Z',
                            requests: 2,
                            errors: 1,
                            error_rate: 0.5,
                            avg_latency_ms: 100,
                        },
                        {
                            timestamp: '2026-04-24T10:00:10Z',
                            requests: 2,
                            errors: 0,
                            error_rate: 0,
                            avg_latency_ms: 200,
                        },
                    ],
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.hasRealtimeSeries).toBe(true)
        expect(result.current.realtimeTotals).toEqual({
            requests: 4,
            errors: 1,
            errorRate: 0.25,
        })
        expect(result.current.errorRateMeter.percentText).toBe('25.00%')
        expect(result.current.readinessMeter.percentText).toBe('50%')
        expect(result.current.latencySeries.map((item) => item.value)).toEqual([100, 200])
        expect(result.current.eventRows.map((item) => item.eventName)).toEqual([
            'event_a',
            'event_b',
        ])
    })

    it('limits realtime latency series to the latest six buckets', async () => {
        const service = createMonitoringService({
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 36, errors: 0, error_rate: 0 },
                routes: [],
                events: {},
                timeseries: {
                    window_seconds: 300,
                    bucket_seconds: 10,
                    points: [
                        { timestamp: '2026-04-24T10:00:00Z', requests: 1, errors: 0, error_rate: 0, avg_latency_ms: 10 },
                        { timestamp: '2026-04-24T10:00:10Z', requests: 2, errors: 0, error_rate: 0, avg_latency_ms: 20 },
                        { timestamp: '2026-04-24T10:00:20Z', requests: 3, errors: 0, error_rate: 0, avg_latency_ms: 30 },
                        { timestamp: '2026-04-24T10:00:30Z', requests: 4, errors: 0, error_rate: 0, avg_latency_ms: 40 },
                        { timestamp: '2026-04-24T10:00:40Z', requests: 5, errors: 0, error_rate: 0, avg_latency_ms: 50 },
                        { timestamp: '2026-04-24T10:00:50Z', requests: 6, errors: 0, error_rate: 0, avg_latency_ms: 60 },
                        { timestamp: '2026-04-24T10:01:00Z', requests: 7, errors: 0, error_rate: 0, avg_latency_ms: 70 },
                        { timestamp: '2026-04-24T10:01:10Z', requests: 8, errors: 0, error_rate: 0, avg_latency_ms: 80 },
                    ],
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.latencySeries.map((item) => item.value)).toEqual([30, 40, 50, 60, 70, 80])
        expect(result.current.realtimeTotals).toEqual({
            requests: 33,
            errors: 0,
            errorRate: 0,
        })
        expect(result.current.realtimeWindowSeconds).toBe(60)
    })

    it('derives realtime window from rendered buckets when source window is zero', async () => {
        const service = createMonitoringService({
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 3, errors: 0, error_rate: 0 },
                routes: [],
                events: {},
                timeseries: {
                    window_seconds: 0,
                    bucket_seconds: 10,
                    points: [
                        { timestamp: '2026-04-24T10:00:00Z', requests: 1, errors: 0, error_rate: 0, avg_latency_ms: 10 },
                        { timestamp: '2026-04-24T10:00:10Z', requests: 2, errors: 0, error_rate: 0, avg_latency_ms: 20 },
                    ],
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.realtimeWindowSeconds).toBe(20)
    })

    it('tracks retry backoff state and clears it after successful retry', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T10:00:00Z'))

        const service = createMonitoringService({
            getMonitoringLive: vi
                .fn()
                .mockRejectedValueOnce(new Error('temporary network issue'))
                .mockResolvedValue({ status: 'ok', timestamp: '2026-04-24T10:00:03Z' }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await act(async () => {
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(result.current.isLoading).toBe(false)
        expect(result.current.errorMessage).toBe('temporary network issue')
        expect(result.current.consecutiveFailures).toBe(1)
        expect(result.current.retryInSeconds).toBeGreaterThan(0)

        await act(async () => {
            vi.advanceTimersByTime(2000)
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(result.current.errorMessage).toBeNull()
        expect(result.current.consecutiveFailures).toBe(0)
        expect(result.current.retryInSeconds).toBe(0)
        expect(service.getMonitoringLive).toHaveBeenCalledTimes(2)
    })

    it('uses fallback error message when a non-Error rejection is thrown', async () => {
        const service = createMonitoringService({
            getMonitoringLive: vi.fn().mockRejectedValueOnce('non-error failure'),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.errorMessage).toBe('Failed to load monitoring data.')
        expect(result.current.consecutiveFailures).toBe(1)
    })

    it('ignores manual refresh calls while a request is already in-flight', async () => {
        const deferredLive = createDeferred<MonitoringLivePayload>()
        const service = createMonitoringService({
            getMonitoringLive: vi.fn().mockReturnValue(deferredLive.promise),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await act(async () => {
            await Promise.resolve()
        })

        act(() => {
            result.current.refreshDashboard()
            result.current.refreshDashboard()
        })

        expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)

        await act(async () => {
            deferredLive.resolve({
                status: 'ok',
                timestamp: '2026-04-24T10:00:00Z',
            })
            await Promise.resolve()
            await Promise.resolve()
        })
    })

    it('skips polling interval refresh while retry backoff window is still active', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T10:00:00Z'))

        const service = createMonitoringService({
            getMonitoringLive: vi
                .fn()
                .mockRejectedValueOnce(new Error('temporary network issue'))
                .mockResolvedValue({ status: 'ok', timestamp: '2026-04-24T10:00:03Z' }),
        })

        renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 1000,
            })
        )

        await act(async () => {
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)

        await act(async () => {
            vi.advanceTimersByTime(1000)
            await Promise.resolve()
        })

        expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)

        await act(async () => {
            vi.advanceTimersByTime(1000)
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(service.getMonitoringLive.mock.calls.length).toBeGreaterThanOrEqual(2)
    })

    it('sorts tied event counts by event name and guards zero-request realtime totals', async () => {
        const service = createMonitoringService({
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 0, errors: 2, error_rate: 1 },
                routes: [
                    {
                        route: '/history/',
                        method: 'GET',
                        total_requests: 0,
                        total_errors: 0,
                        error_rate: 0,
                        avg_latency_ms: 10,
                        max_latency_ms: 15,
                    },
                ],
                events: {
                    event_b: { success: 1 },
                    event_a: { success: 1 },
                },
                timeseries: {
                    window_seconds: 30,
                    bucket_seconds: 10,
                    points: [
                        {
                            timestamp: '2026-04-24T10:00:00Z',
                            requests: 0,
                            errors: 1,
                            error_rate: 0,
                            avg_latency_ms: 10,
                        },
                        {
                            timestamp: '2026-04-24T10:00:10Z',
                            requests: 0,
                            errors: 1,
                            error_rate: 0,
                            avg_latency_ms: 12,
                        },
                    ],
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.realtimeTotals).toEqual({
            requests: 0,
            errors: 2,
            errorRate: 0,
        })
        expect(result.current.eventRows.map((row) => row.eventName)).toEqual(['event_a', 'event_b'])
        expect(result.current.latencyChart.linePoints).not.toBe('')
    })

    it('keeps latency chart generation stable when sparse series has no last point value', async () => {
        const sparsePoints = [
            {
                timestamp: '2026-04-24T10:00:00Z',
                requests: 1,
                errors: 0,
                error_rate: 0,
                avg_latency_ms: 20,
            },
            null,
        ] as unknown as MonitoringStatsPayload['timeseries']['points']

        const service = createMonitoringService({
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 1, errors: 0, error_rate: 0 },
                routes: [],
                events: {},
                timeseries: {
                    window_seconds: 20,
                    bucket_seconds: 10,
                    points: sparsePoints as unknown as MonitoringStatsPayload['timeseries']['points'],
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.latencyChart.linePoints).toContain(',')
        expect(result.current.latencyChart.areaPath).toContain('Z')
    })

    it('falls back to route-level latency data when timeseries points are unavailable', async () => {
        const service = createMonitoringService({
            getMonitoringStats: vi.fn().mockResolvedValue({
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 10, errors: 0, error_rate: 0 },
                routes: [
                    {
                        route: '/history/',
                        method: 'GET',
                        total_requests: 15,
                        total_errors: 1,
                        error_rate: 0.066,
                        avg_latency_ms: 120,
                        max_latency_ms: 200,
                    },
                    {
                        route: '/health',
                        method: 'GET',
                        total_requests: 5,
                        total_errors: 0,
                        error_rate: 0,
                        avg_latency_ms: 60,
                        max_latency_ms: 90,
                    },
                ],
                events: {
                    'auth.login': {
                        success: 1,
                    },
                },
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.hasRealtimeSeries).toBe(false)
        expect(result.current.latencySeries).toHaveLength(2)
        expect(result.current.latencySeries[0]?.label).toBe('/history/')
        expect(result.current.latencySeries[0]?.id).toBe(1)
        expect(result.current.latencySeries).toMatchObject([
            { id: 1, label: '/history/', value: 120, requests: 15 },
            { id: 2, label: '/health', value: 60, requests: 5 },
        ])
        expect(result.current.latencyChart.maxLatency).toBe(120)
        expect(result.current.latencyChart.linePoints).toContain(',')
    })

    it('uses authenticated snapshot service when available to avoid extra per-endpoint orchestration', async () => {
        const getMonitoringLive = vi.fn().mockResolvedValue({
            status: 'ok',
            timestamp: '2026-04-24T10:00:00Z',
        })
        const getMonitoringAuthenticatedSnapshot = vi.fn().mockResolvedValue({
            accessDecision: { allowed: true, reason: 'ok' },
            readyPayload: {
                status: 'ok',
                timestamp: '2026-04-24T10:00:01Z',
                checks: [{ name: 'database', status: 'ok', latency_ms: 3, is_critical: true }],
            },
            statsPayload: {
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 1, errors: 0, error_rate: 0 },
                routes: [],
                events: {},
            },
        })

        const service: MonitoringDashboardService = {
            getMonitoringLive,
            getMonitoringAccess: vi.fn(),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
            getMonitoringAuthenticatedSnapshot,
        }

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(getMonitoringLive).toHaveBeenCalledTimes(1)
        expect(getMonitoringAuthenticatedSnapshot).toHaveBeenCalledTimes(1)
        expect(service.getMonitoringAccess).not.toHaveBeenCalled()
        expect(service.getMonitoringReady).not.toHaveBeenCalled()
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
    })

    it('stops bootstrap flow when snapshot denies access and does not start stream', async () => {
        const getMonitoringLive = vi.fn().mockResolvedValue({
            status: 'ok',
            timestamp: '2026-04-24T10:00:00Z',
        })
        const getMonitoringAuthenticatedSnapshot = vi.fn().mockResolvedValue({
            accessDecision: { allowed: false, reason: 'inactive' },
            readyPayload: null,
            statsPayload: null,
        })
        const getMonitoringStatsStream = vi.fn()
        const service: MonitoringDashboardService = {
            getMonitoringLive,
            getMonitoringAccess: vi.fn(),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
            getMonitoringAuthenticatedSnapshot,
            getMonitoringStatsStream,
        }

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(getMonitoringLive).toHaveBeenCalledTimes(1)
        expect(getMonitoringAuthenticatedSnapshot).toHaveBeenCalledTimes(1)
        expect(getMonitoringStatsStream).not.toHaveBeenCalled()
        expect(service.getMonitoringAccess).not.toHaveBeenCalled()
        expect(service.getMonitoringReady).not.toHaveBeenCalled()
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
    })

    it('bootstraps with snapshot once and keeps interval polling paused while stream is active', async () => {
        vi.useFakeTimers()
        const streamClose = vi.fn()
        const getMonitoringLive = vi.fn().mockResolvedValue({
            status: 'ok',
            timestamp: '2026-04-24T10:00:00Z',
        })
        const getMonitoringAuthenticatedSnapshot = vi.fn().mockResolvedValue({
            accessDecision: { allowed: true, reason: 'ok' },
            readyPayload: {
                status: 'ok',
                timestamp: '2026-04-24T10:00:01Z',
                checks: [{ name: 'database', status: 'ok', latency_ms: 3, is_critical: true }],
            },
            statsPayload: {
                status: 'ok',
                generated_at: '2026-04-24T10:00:02Z',
                totals: { requests: 1, errors: 0, error_rate: 0 },
                routes: [],
                events: {},
            },
        })
        const getMonitoringStatsStream = vi.fn().mockResolvedValue({ close: streamClose })
        const service: MonitoringDashboardService = {
            getMonitoringLive,
            getMonitoringAccess: vi.fn(),
            getMonitoringReady: vi.fn(),
            getMonitoringStats: vi.fn(),
            getMonitoringAuthenticatedSnapshot,
            getMonitoringStatsStream,
        }

        const { result, unmount } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 1000,
            })
        )

        await act(async () => {
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(result.current.isLoading).toBe(false)
        expect(getMonitoringAuthenticatedSnapshot).toHaveBeenCalledTimes(1)
        expect(getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        expect(getMonitoringLive).toHaveBeenCalledTimes(1)

        await act(async () => {
            vi.advanceTimersByTime(3000)
            await Promise.resolve()
            await Promise.resolve()
        })

        expect(getMonitoringAuthenticatedSnapshot).toHaveBeenCalledTimes(1)
        expect(getMonitoringLive).toHaveBeenCalledTimes(1)

        unmount()
        expect(streamClose).toHaveBeenCalledTimes(1)
    })

    it('keeps using active stream on refresh and skips stats snapshot fallback', async () => {
        const streamClose = vi.fn()
        const service = createMonitoringService({
            getMonitoringStatsStream: vi.fn().mockResolvedValue({ close: streamClose }),
            getMonitoringStats: vi.fn(),
        })

        const { result, unmount } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        })

        act(() => {
            result.current.refreshDashboard()
        })

        await waitFor(() => {
            expect(service.getMonitoringAccess).toHaveBeenCalledTimes(2)
        })

        expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        expect(service.getMonitoringStats).not.toHaveBeenCalled()

        unmount()
        expect(streamClose).toHaveBeenCalledTimes(1)
    })

    it('subscribes to realtime stream for stats when service supports it', async () => {
        const streamClose = vi.fn()
        const streamPayload = makeStreamStatsPayload()
        const service = createMonitoringService({
            getMonitoringStatsStream: vi.fn().mockImplementation(async ({ onPayload }) => {
                onPayload(streamPayload)
                return { close: streamClose }
            }),
            getMonitoringStats: vi.fn(),
        })

        const { result, unmount } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        expect(service.getMonitoringStats).not.toHaveBeenCalled()
        expect(result.current.statsPayload?.totals.requests).toBe(200)

        unmount()
        expect(streamClose).toHaveBeenCalledTimes(1)
    })

    it('ignores stream errors after the hook is unmounted', async () => {
        const streamClose = vi.fn()
        let capturedError: ((error: Error) => void) | undefined
        const service = createMonitoringService({
            getMonitoringStatsStream: vi.fn().mockImplementation(async ({ onError }) => {
                capturedError = onError
                return { close: streamClose }
            }),
            getMonitoringStats: vi.fn(),
        })

        const { unmount } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        })

        unmount()

        act(() => {
            capturedError?.(new Error('stream error after unmount'))
        })

        expect(streamClose).toHaveBeenCalledTimes(1)
    })

    it('marks data as stale immediately when stale threshold is already exceeded', async () => {
        const now = vi.spyOn(Date, 'now')

        const service = createMonitoringService()
        now.mockReturnValue(new Date('2026-04-24T10:00:00Z').getTime())

        try {
            const { result, rerender } = renderHook(
                ({ autoRefreshIntervalMs }) =>
                    useMonitoringDashboardModel({
                        monitoringService: service,
                        autoRefreshIntervalMs,
                    }),
                {
                    initialProps: {
                        autoRefreshIntervalMs: 60000,
                    },
                }
            )

            await waitFor(() => {
                expect(result.current.isLoading).toBe(false)
            })
            expect(result.current.isDataStale).toBe(false)

            now.mockReturnValue(new Date('2026-04-24T10:00:20Z').getTime())
            rerender({ autoRefreshIntervalMs: 1000 })

            await waitFor(() => {
                expect(result.current.isDataStale).toBe(true)
            })
        } finally {
            now.mockRestore()
        }
    })

    it('defaults visibility to true when document is unavailable', () => {
        const originalDocument = globalThis.document

        try {
            vi.stubGlobal('document', undefined)
            expect(getIsPageVisible()).toBe(true)
        } finally {
            vi.stubGlobal('document', originalDocument)
        }
    })

    it('derives visibility from document visibilityState', () => {
        const originalVisibilityDescriptor = Object.getOwnPropertyDescriptor(document, 'visibilityState')
        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => 'hidden',
        })

        try {
            expect(getIsPageVisible()).toBe(false)

            Object.defineProperty(document, 'visibilityState', {
                configurable: true,
                get: () => 'visible',
            })

            expect(getIsPageVisible()).toBe(true)
        } finally {
            if (originalVisibilityDescriptor) {
                Object.defineProperty(document, 'visibilityState', originalVisibilityDescriptor)
            } else {
                Reflect.deleteProperty(document, 'visibilityState')
            }
        }
    })

    it('pauses interval polling when tab is hidden and refreshes when visible again', async () => {
        vi.useFakeTimers()

        const originalVisibilityDescriptor = Object.getOwnPropertyDescriptor(document, 'visibilityState')
        let currentVisibilityState: DocumentVisibilityState = 'visible'
        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => currentVisibilityState,
        })

        const service = createMonitoringService()

        try {
            renderHook(() =>
                useMonitoringDashboardModel({
                    monitoringService: service,
                    autoRefreshIntervalMs: 1000,
                })
            )

            await act(async () => {
                await Promise.resolve()
                await Promise.resolve()
            })

            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)

            await act(async () => {
                currentVisibilityState = 'hidden'
                document.dispatchEvent(new Event('visibilitychange'))
            })

            await act(async () => {
                vi.advanceTimersByTime(3000)
                await Promise.resolve()
            })

            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)

            await act(async () => {
                currentVisibilityState = 'visible'
                document.dispatchEvent(new Event('visibilitychange'))
                await Promise.resolve()
                await Promise.resolve()
            })

            expect(service.getMonitoringLive.mock.calls.length).toBeGreaterThanOrEqual(2)
        } finally {
            if (originalVisibilityDescriptor) {
                Object.defineProperty(document, 'visibilityState', originalVisibilityDescriptor)
            } else {
                Reflect.deleteProperty(document, 'visibilityState')
            }
        }
    })

    it('skips attaching visibility listener when document becomes unavailable', async () => {
        const initialService = createMonitoringService()
        const rerenderService = createMonitoringService()

        const { rerender } = renderHook(
            ({ monitoringService }) =>
                useMonitoringDashboardModel({
                    monitoringService,
                    autoRefreshIntervalMs: 60000,
                }),
            {
                initialProps: {
                    monitoringService: initialService,
                },
            }
        )

        await waitFor(() => {
            expect(initialService.getMonitoringLive).toHaveBeenCalledTimes(1)
        })

        const originalDocument = globalThis.document
        try {
            vi.stubGlobal('document', undefined)

            rerender({
                monitoringService: rerenderService,
            })

            await act(async () => {
                await Promise.resolve()
                await Promise.resolve()
            })

            expect(rerenderService.getMonitoringLive).toHaveBeenCalledTimes(1)
        } finally {
            vi.stubGlobal('document', originalDocument)
        }
    })

    it('marks data stale when stale timeout fires', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T10:00:00Z'))

        const originalVisibilityDescriptor = Object.getOwnPropertyDescriptor(document, 'visibilityState')
        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => 'hidden',
        })

        try {
            const service = createMonitoringService()
            const { result } = renderHook(() =>
                useMonitoringDashboardModel({
                    monitoringService: service,
                    autoRefreshIntervalMs: 1000,
                })
            )

            await act(async () => {
                await Promise.resolve()
                await Promise.resolve()
            })
            expect(result.current.isLoading).toBe(false)
            expect(result.current.isDataStale).toBe(false)

            await act(async () => {
                vi.advanceTimersByTime(15001)
                await Promise.resolve()
            })

            expect(result.current.isDataStale).toBe(true)
        } finally {
            if (originalVisibilityDescriptor) {
                Object.defineProperty(document, 'visibilityState', originalVisibilityDescriptor)
            } else {
                Reflect.deleteProperty(document, 'visibilityState')
            }
        }
    })

    it('retries stream connection after stream-level error and resumes periodic loading', async () => {
        const streamClose = vi.fn()
        let capturedError: ((error: Error) => void) | undefined
        const service = createMonitoringService({
            getMonitoringStatsStream: vi.fn().mockImplementation(async ({ onError }) => {
                capturedError = onError
                return { close: streamClose }
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 1000,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        })

        act(() => {
            capturedError?.(new Error('stream interrupted'))
        })
        expect(streamClose).toHaveBeenCalledTimes(1)
        expect(result.current.consecutiveFailures).toBe(1)

        act(() => {
            result.current.refreshDashboard()
        })

        await waitFor(() => {
            expect(
                (service.getMonitoringStatsStream as ReturnType<typeof vi.fn>).mock.calls.length
            ).toBe(2)
        })
    })

    it('suppresses error banner message when stream closes unexpectedly', async () => {
        const streamClose = vi.fn()
        let capturedError: ((error: Error) => void) | undefined
        const service = createMonitoringService({
            getMonitoringStatsStream: vi.fn().mockImplementation(async ({ onError }) => {
                capturedError = onError
                return { close: streamClose }
            }),
        })

        const { result } = renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 60000,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringStatsStream).toHaveBeenCalledTimes(1)
        })

        act(() => {
            capturedError?.(new Error('Monitoring stream closed unexpectedly.'))
        })

        expect(result.current.errorMessage).toBeNull()
        expect(streamClose).toHaveBeenCalledTimes(1)
        expect(result.current.consecutiveFailures).toBe(1)
    })
})
