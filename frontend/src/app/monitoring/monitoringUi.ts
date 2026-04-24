const ACCESS_REASON_MESSAGES: Record<string, string> = {
    unauthenticated: 'Please log in to continue.',
    unverified: 'A verified account is required to access monitoring.',
    no_account: 'Monitoring account access is required for this page.',
    inactive: 'Your monitoring account is currently inactive.',
    ok: 'Monitoring access granted.',
}

export function formatTimestamp(value: string): string {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return value
    }

    return parsed.toLocaleString('en-US', {
        hour12: false,
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    })
}

export function formatPercent(value: number): string {
    if (!Number.isFinite(value)) {
        return '0.00%'
    }

    return `${(value * 100).toFixed(2)}%`
}

export function formatTimeLabel(value: string): string {
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
        return value
    }
    return parsed.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    })
}

export function statusBadgeClass(status: string): string {
    const normalizedStatus = status.toLowerCase()
    if (normalizedStatus === 'ok' || normalizedStatus === 'success') {
        return 'border border-blue-200 bg-blue-50 text-blue-700'
    }
    if (normalizedStatus === 'degraded') {
        return 'border border-red-300 bg-red-50 text-red-700'
    }
    if (normalizedStatus === 'down' || normalizedStatus === 'error' || normalizedStatus === 'exception') {
        return 'border border-red-400 bg-red-50 text-red-700'
    }
    return 'border border-gray-300 bg-gray-100 text-gray-700'
}

export function resolveAccessMessage(reason: string): string {
    return ACCESS_REASON_MESSAGES[reason] ?? `Access status: ${reason}`
}

export function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value))
}

