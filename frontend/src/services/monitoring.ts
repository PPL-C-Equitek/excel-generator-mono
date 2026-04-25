import { fetchAPI } from '@/lib/api'
import { getValidAccessToken } from '@/lib/auth'
import {
    mapMonitoringAuthenticatedSnapshotResponse,
    mapMonitoringAccessResponse,
    mapMonitoringLiveResponse,
    mapMonitoringReadyResponse,
    mapMonitoringStatsResponse,
} from './monitoringAdapter'
import type {
    MonitoringAuthenticatedSnapshot,
    MonitoringAccessDecision,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
} from './monitoring.types'
export type {
    MonitoringAuthenticatedSnapshot,
    MonitoringAccessDecision,
    MonitoringCheck,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringRouteStat,
    MonitoringStatsPayload,
    MonitoringTimeseriesPoint,
} from './monitoring.types'

export type MonitoringStatsStreamHandle = {
    close: () => void
}

export type MonitoringStatsStreamOptions = {
    onPayload: (payload: MonitoringStatsPayload) => void
    onError?: (error: Error) => void
    accessToken?: string
    intervalSeconds?: number
    maxEvents?: number
}

const MONITORING_AUTH_REQUIRED_MESSAGE = 'Authentication credentials were not provided.'

export async function getMonitoringAuthToken(): Promise<string> {
    const accessToken = await getValidAccessToken()
    if (!accessToken) {
        throw new Error(MONITORING_AUTH_REQUIRED_MESSAGE)
    }
    return accessToken
}

async function fetchMonitoringWithAuth(endpoint: string, accessToken?: string): Promise<unknown> {
    const token = accessToken ?? await getMonitoringAuthToken()
    return fetchAPI(endpoint, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${token}`,
        },
    })
}

function parseMonitoringSseEventBlock(rawEvent: string): string | null {
    const lines = rawEvent.split(/\r?\n/)
    const dataSegments: string[] = []

    for (const line of lines) {
        if (!line.startsWith('data:')) {
            continue
        }
        dataSegments.push(line.slice(5).trimStart())
    }

    if (dataSegments.length === 0) {
        return null
    }

    return dataSegments.join('')
}

function splitMonitoringSseFrames(
    buffer: string,
): { frames: string[]; remainder: string } {
    const frames = buffer.split(/\r?\n\r?\n/)
    if (frames.length === 1) {
        return { frames: [], remainder: buffer }
    }

    const remainder = frames.pop() ?? ''
    return { frames, remainder }
}

async function collectMonitoringStreamPayloads({
    onPayload,
    onError,
    accessToken,
    intervalSeconds,
    maxEvents,
}: MonitoringStatsStreamOptions): Promise<MonitoringStatsStreamHandle> {
    const token = await getMonitoringAuthToken()
    const safeAccessToken = accessToken ?? token
    const interval = Math.max(1, Number(intervalSeconds ?? 2))
    const normalizedMaxEvents = Number.isFinite(maxEvents ?? NaN) ? Number(maxEvents) : NaN
    const hasMaxEvents = Number.isFinite(normalizedMaxEvents) && normalizedMaxEvents > 0
    const streamURL = `monitoring/stream/?interval_seconds=${interval}${
        hasMaxEvents ? `&max_events=${Math.floor(normalizedMaxEvents)}` : ''
    }`
    const controller = new AbortController()

    const response = await fetch(streamURL, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${safeAccessToken}`,
            Accept: 'text/event-stream',
        },
        signal: controller.signal,
    })

    if (!response.ok) {
        throw new Error('Monitoring stream is unavailable.')
    }

    if (!response.body) {
        throw new Error('Monitoring stream response has no readable body.')
    }

    const decoder = new TextDecoder()
    const reader = response.body.getReader()

    const close = () => {
        if (!controller.signal.aborted) {
            controller.abort()
        }
    }

    let buffer = ''
    const parseAndPublish = async () => {
        try {
            while (true) {
                const result = await reader.read()
                if (result.done) {
                    break
                }

                buffer += decoder.decode(result.value, { stream: true })
                const parsed = splitMonitoringSseFrames(buffer)
                buffer = parsed.remainder

                for (const frame of parsed.frames) {
                    const data = parseMonitoringSseEventBlock(frame)
                    if (!data) {
                        continue
                    }

                    const payload = mapMonitoringStatsResponse(JSON.parse(data))
                    onPayload(payload)
                }
            }

            buffer = decoder.decode()
            const data = parseMonitoringSseEventBlock(buffer)
            if (data) {
                const payload = mapMonitoringStatsResponse(JSON.parse(data))
                onPayload(payload)
            }
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                return
            }
            if (error instanceof Error) {
                onError?.(error)
            } else {
                onError?.(new Error('Monitoring stream parse failed.'))
            }
        } finally {
            try {
                await reader.cancel()
            } catch {
                // ignore
            }
        }
    }

    void parseAndPublish()
    return { close }
}

export async function getMonitoringLive(): Promise<MonitoringLivePayload> {
    const payload = await fetchAPI('monitoring/live/', {
        method: 'GET',
    })
    return mapMonitoringLiveResponse(payload)
}

export async function getMonitoringAccess(accessToken?: string): Promise<MonitoringAccessDecision> {
    return mapMonitoringAccessResponse(
        await fetchMonitoringWithAuth('monitoring/access/', accessToken)
    )
}

export async function getMonitoringReady(accessToken?: string): Promise<MonitoringReadyPayload> {
    return mapMonitoringReadyResponse(
        await fetchMonitoringWithAuth('monitoring/ready/', accessToken)
    )
}

export async function getMonitoringStats(accessToken?: string): Promise<MonitoringStatsPayload> {
    return mapMonitoringStatsResponse(
        await fetchMonitoringWithAuth('monitoring/stats/', accessToken)
    )
}

export async function getMonitoringStatsStream(
    options: MonitoringStatsStreamOptions,
): Promise<MonitoringStatsStreamHandle> {
    return collectMonitoringStreamPayloads(options)
}

export async function getMonitoringAuthenticatedSnapshot(): Promise<MonitoringAuthenticatedSnapshot> {
    const accessToken = await getMonitoringAuthToken()
    const payload = await fetchMonitoringWithAuth('monitoring/snapshot/', accessToken)

    return mapMonitoringAuthenticatedSnapshotResponse(payload)
}
