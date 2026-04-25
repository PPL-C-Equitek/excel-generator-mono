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

    return dataSegments.join('\n')
}

function splitMonitoringSseFrames(
    buffer: string,
): { frames: string[]; remainder: string } {
    const frames = buffer.split(/\r?\n\r?\n/)
    if (frames.length === 1) {
        return { frames: [], remainder: buffer }
    }

    const remainder = frames.at(-1) ?? ''
    const payloadFrames = frames.slice(0, -1)

    return {
        frames: payloadFrames.filter((frame) => frame.trim() !== ''),
        remainder,
    }
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
    const controller = new AbortController()
    const streamURL = buildMonitoringStreamUrl({ intervalSeconds, maxEvents })
    const response = await fetchMonitoringStreamResponse({
        streamURL,
        safeAccessToken,
        controller,
    })

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()

    const close = () => {
        if (!controller.signal.aborted) {
            controller.abort()
        }
    }

    void parseMonitoringStatsStream({
        reader,
        decoder,
        onPayload,
        onError,
        abortSignal: controller.signal,
    })
    return { close }
}

function parseMonitoringFrame(frame: string, onPayload: (payload: MonitoringStatsPayload) => void): void {
    const data = parseMonitoringSseEventBlock(frame)
    if (!data) {
        return
    }

    const payload = mapMonitoringStatsResponse(JSON.parse(data))
    onPayload(payload)
}

async function parseMonitoringStatsFrames({
    reader,
    decoder,
    onFrame,
}: {
    reader: ReadableStreamDefaultReader<Uint8Array>
    decoder: TextDecoder
    onFrame: (frame: string) => void
}): Promise<string> {
    let buffer = ''

    while (true) {
        const result = await reader.read()
        if (result.done) {
            return buffer
        }

        buffer += decoder.decode(result.value, { stream: true })
        const parsed = splitMonitoringSseFrames(buffer)
        buffer = parsed.remainder

        for (const frame of parsed.frames) {
            onFrame(frame)
        }
    }
}

function buildMonitoringStreamUrl({
    intervalSeconds,
    maxEvents,
}: {
    intervalSeconds?: number
    maxEvents?: number
}): string {
    const interval = buildMonitoringStreamInterval(intervalSeconds)
    const normalizedMaxEvents = getValidatedPositiveInteger(maxEvents)
    const maxEventsQuery = normalizedMaxEvents === undefined ? '' : `&max_events=${normalizedMaxEvents}`

    return `monitoring/stream/?interval_seconds=${interval}${maxEventsQuery}`
}

function buildMonitoringStreamInterval(intervalSeconds?: number): number {
    const intervalCandidate = getFiniteValue(intervalSeconds)
    return Number.isFinite(intervalCandidate)
        ? Math.max(1, Math.floor(intervalCandidate))
        : 1
}

function getValidatedPositiveInteger(value?: number): number | undefined {
    const candidate = getFiniteValue(value)
    if (!Number.isFinite(candidate) || candidate <= 0) {
        return undefined
    }

    return Math.floor(candidate)
}

function getFiniteValue(value?: number): number {
    return Number.isFinite(value) ? value : Number.NaN
}

async function fetchMonitoringStreamResponse({
    streamURL,
    safeAccessToken,
    controller,
}: {
    streamURL: string
    safeAccessToken: string
    controller: AbortController
}): Promise<Response> {
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

    return response
}

async function parseMonitoringStatsStream({
    reader,
    decoder,
    onPayload,
    onError,
    abortSignal,
}: {
    reader: ReadableStreamDefaultReader<Uint8Array>
    decoder: TextDecoder
    onPayload: (payload: MonitoringStatsPayload) => void
    onError?: (error: Error) => void
    abortSignal: AbortSignal
}): Promise<void> {
    try {
        const finalBuffer = await parseMonitoringStatsFrames({
            reader,
            decoder,
            onFrame: (frame) => parseMonitoringFrame(frame, onPayload),
        })

        reportUnexpectedStreamClosure({
            abortSignal,
            onError,
        })
        publishTrailingFramePayload({
            rawFrame: finalBuffer,
            onPayload,
        })
    } catch (error) {
        onStreamParseError({ error, onError })
    } finally {
        await closeStreamReader(reader)
    }
}

function publishTrailingFramePayload({
    rawFrame,
    onPayload,
}: {
    rawFrame: string
    onPayload: (payload: MonitoringStatsPayload) => void
}) {
    const trailingData = parseMonitoringSseEventBlock(rawFrame)
    if (!trailingData) {
        return
    }

    try {
        const payload = mapMonitoringStatsResponse(JSON.parse(trailingData))
        onPayload(payload)
    } catch {
        // ignore malformed trailing fragments after close
    }
}

function reportUnexpectedStreamClosure({
    abortSignal,
    onError,
}: {
    abortSignal: AbortSignal
    onError?: (error: Error) => void
}) {
    if (abortSignal.aborted) {
        return
    }

    onError?.(new Error('Monitoring stream closed unexpectedly.'))
}

function onStreamParseError({
    error,
    onError,
}: {
    error: unknown
    onError?: (error: Error) => void
}) {
    if (error instanceof DOMException && error.name === 'AbortError') {
        return
    }

    onError?.(normalizeMonitoringStreamError(error))
}

function normalizeMonitoringStreamError(error: unknown): Error {
    if (error instanceof Error) {
        return error
    }

    return new Error('Monitoring stream parse failed.')
}

async function closeStreamReader(reader: ReadableStreamDefaultReader<Uint8Array>) {
    try {
        await reader.cancel()
    } catch {
        // ignore
    }
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
