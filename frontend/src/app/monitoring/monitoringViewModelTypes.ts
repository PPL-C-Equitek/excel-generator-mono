export type RealtimeTotals = {
    requests: number
    errors: number
    errorRate: number
} | null

export type LatencySeriesPoint = {
    id: number
    label: string
    value: number
    requests: number
}

export type LatencyChartPoint = {
    id: number
    x: number
    y: number
    xLabel: string
    showLabel: boolean
}

export type LatencyChartModel = {
    linePoints: string
    areaPath: string
    maxLatency: number
    maxRequests: number
    points: LatencyChartPoint[]
}

export type ErrorRateMeter = {
    percentText: string
    progressLength: number
    colorClass: string
}

export type ReadinessMeter = {
    percentText: string
    progressLength: number
    colorClass: string
    healthyChecks: number
    totalChecks: number
}

export type EventRow = {
    eventName: string
    outcome: string
    count: number
}

export type AuthEventSummaryRow = EventRow & {
    eventWidth: string
}

export type RouteSummaryRow = {
    route: string
    method: string
    totalRequests: number
    totalErrors: number
    avgLatencyMs: number
    requestWidth: string
}
