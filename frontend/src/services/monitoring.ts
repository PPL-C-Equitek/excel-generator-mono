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

async function fetchMonitoringWithAuth(endpoint: string): Promise<unknown> {
    const accessToken = await getValidAccessToken()
    if (!accessToken) {
        throw new Error(MONITORING_AUTH_REQUIRED_MESSAGE)
    }

    return fetchAPI(endpoint, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${accessToken}`,
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
