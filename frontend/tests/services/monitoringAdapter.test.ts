import { describe, expect, it } from 'vitest'
import {
    mapMonitoringAccessResponse,
    mapMonitoringLiveResponse,
    mapMonitoringReadyResponse,
    mapMonitoringStatsResponse,
} from '../../src/services/monitoringAdapter'

describe('monitoring adapter', () => {
    it('maps live and access payloads with sane defaults', () => {
        expect(mapMonitoringLiveResponse(null)).toEqual({
            status: 'unknown',
            timestamp: '',
        })

        expect(mapMonitoringAccessResponse({})).toEqual({
            allowed: false,
            reason: 'unauthenticated',
        })
    })

    it('maps ready payload checks and keeps optional message when available', () => {
        expect(
            mapMonitoringReadyResponse({
                status: 'ok',
                timestamp: '2026-04-24T10:00:00Z',
                checks: [
                    {
                        name: 'database',
                        status: 'ok',
                        latency_ms: 2,
                        is_critical: true,
                        message: 'healthy',
                    },
                    {
                        name: null,
                    },
                ],
            })
        ).toEqual({
            status: 'ok',
            timestamp: '2026-04-24T10:00:00Z',
            checks: [
                {
                    name: 'database',
                    status: 'ok',
                    latency_ms: 2,
                    is_critical: true,
                    message: 'healthy',
                },
                {
                    name: 'unknown',
                    status: 'unknown',
                    latency_ms: 0,
                    is_critical: true,
                },
            ],
        })
    })

    it('returns empty checks when ready payload checks is not an array', () => {
        expect(
            mapMonitoringReadyResponse({
                status: 'ok',
                timestamp: 'x',
                checks: 'invalid',
            })
        ).toEqual({
            status: 'ok',
            timestamp: 'x',
            checks: [],
        })
    })

    it('maps stats payload and ignores non-record event outcomes', () => {
        expect(
            mapMonitoringStatsResponse({
                status: 'ok',
                generated_at: '2026-04-24T10:00:00Z',
                totals: {
                    requests: 1,
                    errors: 0,
                    error_rate: 0,
                },
                routes: [
                    {
                        route: '/history',
                        method: 'GET',
                        total_requests: 1,
                        total_errors: 0,
                        error_rate: 0,
                        avg_latency_ms: 12,
                        max_latency_ms: 12,
                    },
                ],
                events: {
                    login: {
                        success: 3,
                    },
                    invalid_event: 'bad',
                },
                timeseries: {
                    window_seconds: 60,
                    bucket_seconds: 10,
                    points: 'invalid',
                },
            })
        ).toEqual({
            status: 'ok',
            generated_at: '2026-04-24T10:00:00Z',
            totals: {
                requests: 1,
                errors: 0,
                error_rate: 0,
            },
            routes: [
                {
                    route: '/history',
                    method: 'GET',
                    total_requests: 1,
                    total_errors: 0,
                    error_rate: 0,
                    avg_latency_ms: 12,
                    max_latency_ms: 12,
                },
            ],
            events: {
                login: {
                    success: 3,
                },
            },
            timeseries: {
                window_seconds: 60,
                bucket_seconds: 10,
                points: [],
            },
        })
    })

    it('returns empty maps for malformed stats payload root', () => {
        expect(mapMonitoringStatsResponse('invalid')).toEqual({
            status: 'unknown',
            generated_at: '',
            totals: {
                requests: 0,
                errors: 0,
                error_rate: 0,
            },
            routes: [],
            events: {},
            timeseries: undefined,
        })
    })
})

