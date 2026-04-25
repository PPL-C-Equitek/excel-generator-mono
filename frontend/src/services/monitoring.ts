import { fetchAPI } from '@/lib/api'
import { getValidAccessToken } from '@/lib/auth'
import {
    mapMonitoringAccessResponse,
    mapMonitoringLiveResponse,
    mapMonitoringReadyResponse,
    mapMonitoringStatsResponse,
} from './monitoringAdapter'
import type {
    MonitoringAccessDecision,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
} from './monitoring.types'
export type {
    MonitoringAccessDecision,
    MonitoringCheck,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringRouteStat,
    MonitoringStatsPayload,
    MonitoringTimeseriesPoint,
} from './monitoring.types'

const MONITORING_AUTH_REQUIRED_MESSAGE = 'Authentication credentials were not provided.'

export type MonitoringAuthenticatedSnapshot = {
    accessDecision: MonitoringAccessDecision
    readyPayload: MonitoringReadyPayload | null
    statsPayload: MonitoringStatsPayload | null
}

async function getMonitoringAuthToken(): Promise<string> {
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

export async function getMonitoringLive(): Promise<MonitoringLivePayload> {
    const payload = await fetchAPI('monitoring/live/', {
        method: 'GET',
    })
    return mapMonitoringLiveResponse(payload)
}

export async function getMonitoringAccess(): Promise<MonitoringAccessDecision> {
    return mapMonitoringAccessResponse(
        await fetchMonitoringWithAuth('monitoring/access/')
    )
}

export async function getMonitoringReady(): Promise<MonitoringReadyPayload> {
    return mapMonitoringReadyResponse(
        await fetchMonitoringWithAuth('monitoring/ready/')
    )
}

export async function getMonitoringStats(): Promise<MonitoringStatsPayload> {
    return mapMonitoringStatsResponse(
        await fetchMonitoringWithAuth('monitoring/stats/')
    )
}

export async function getMonitoringAuthenticatedSnapshot(): Promise<MonitoringAuthenticatedSnapshot> {
    const accessToken = await getMonitoringAuthToken()

    const accessDecision = mapMonitoringAccessResponse(
        await fetchMonitoringWithAuth('monitoring/access/', accessToken)
    )

    if (!accessDecision.allowed) {
        return {
            accessDecision,
            readyPayload: null,
            statsPayload: null,
        }
    }

    const [readyPayload, statsPayload] = await Promise.all([
        fetchMonitoringWithAuth('monitoring/ready/', accessToken),
        fetchMonitoringWithAuth('monitoring/stats/', accessToken),
    ])

    return {
        accessDecision,
        readyPayload: mapMonitoringReadyResponse(readyPayload),
        statsPayload: mapMonitoringStatsResponse(statsPayload),
    }
}
