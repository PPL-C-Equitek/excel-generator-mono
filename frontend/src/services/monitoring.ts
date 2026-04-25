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

export async function getMonitoringAuthenticatedSnapshot(): Promise<MonitoringAuthenticatedSnapshot> {
    const accessToken = await getMonitoringAuthToken()
    const payload = await fetchMonitoringWithAuth('monitoring/snapshot/', accessToken)

    return mapMonitoringAuthenticatedSnapshotResponse(payload)
}
