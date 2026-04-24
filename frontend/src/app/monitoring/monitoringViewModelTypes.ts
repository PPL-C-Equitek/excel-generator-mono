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

export type LatencyChartModel = {
    linePoints: string
    areaPath: string
    maxLatency: number
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

