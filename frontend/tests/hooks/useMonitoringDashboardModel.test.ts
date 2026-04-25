import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

describe('useMonitoringDashboardModel', () => {
    beforeEach(() => {
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

    it('polls monitoring endpoints on the configured interval', async () => {
        const service = createMonitoringService()

        renderHook(() =>
            useMonitoringDashboardModel({
                monitoringService: service,
                autoRefreshIntervalMs: 20,
            })
        )

        await waitFor(() => {
            expect(service.getMonitoringLive).toHaveBeenCalledTimes(1)
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
        const sparsePoints: Array<{
            timestamp: string
            requests: number
            errors: number
            error_rate: number
            avg_latency_ms: number
        }> = [
            {
                timestamp: '2026-04-24T10:00:00Z',
                requests: 1,
                errors: 0,
                error_rate: 0,
                avg_latency_ms: 20,
            },
        ]
        sparsePoints.length = 2

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

    it('marks data stale immediately when effect reruns after threshold has already passed', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-04-24T10:00:00Z'))

        const originalVisibilityDescriptor = Object.getOwnPropertyDescriptor(document, 'visibilityState')
        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            get: () => 'hidden',
        })

        try {
            const service = createMonitoringService()
            const { result, rerender } = renderHook(
                ({ intervalMs }) =>
                    useMonitoringDashboardModel({
                        monitoringService: service,
                        autoRefreshIntervalMs: intervalMs,
                    }),
                {
                    initialProps: {
                        intervalMs: 1000,
                    },
                }
            )

            await act(async () => {
                await Promise.resolve()
                await Promise.resolve()
            })
            expect(result.current.isLoading).toBe(false)
            expect(result.current.isDataStale).toBe(false)

            act(() => {
                vi.setSystemTime(new Date('2026-04-24T10:00:20Z'))
            })

            rerender({
                intervalMs: 2000,
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
})
