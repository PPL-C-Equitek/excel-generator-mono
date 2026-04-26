export type MonitoringAccessDecision = {
    allowed: boolean
    reason: string
}

export type MonitoringLivePayload = {
    status: string
    timestamp: string
}

export type MonitoringCheck = {
    name: string
    status: string
    latency_ms: number
    is_critical: boolean
    message?: string
}

export type MonitoringReadyPayload = {
    status: string
    timestamp: string
    checks: MonitoringCheck[]
}

export type MonitoringRouteStat = {
    route: string
    method: string
    total_requests: number
    total_errors: number
    error_rate: number
    avg_latency_ms: number
    max_latency_ms: number
}

export type MonitoringTimeseriesPoint = {
    timestamp: string
    requests: number
    errors: number
    error_rate: number
    avg_latency_ms: number
}

export type MonitoringStatsPayload = {
    status: string
    generated_at: string
    totals: {
        requests: number
        errors: number
        error_rate: number
    }
    routes: MonitoringRouteStat[]
    events: Record<string, Record<string, number>>
    timeseries?: {
        window_seconds: number
        bucket_seconds: number
        points: MonitoringTimeseriesPoint[]
    }
}

export type MonitoringAuthenticatedSnapshot = {
    accessDecision: MonitoringAccessDecision
    readyPayload: MonitoringReadyPayload | null
    statsPayload: MonitoringStatsPayload | null
}
