import { fetchAPI } from '@/lib/api'
import { getValidAccessToken } from '@/lib/auth'

const MONITORING_AUTH_REQUIRED_MESSAGE = 'Authentication credentials were not provided.'

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
    points: Array<{
      timestamp: string
      requests: number
      errors: number
      error_rate: number
      avg_latency_ms: number
    }>
  }
}

async function fetchMonitoringWithAuth<T>(endpoint: string): Promise<T> {
  const accessToken = await getValidAccessToken()
  if (!accessToken) {
    throw new Error(MONITORING_AUTH_REQUIRED_MESSAGE)
  }

  return fetchAPI(endpoint, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  }) as Promise<T>
}

export async function getMonitoringLive(): Promise<MonitoringLivePayload> {
  return fetchAPI('monitoring/live/', {
    method: 'GET',
  }) as Promise<MonitoringLivePayload>
}

export async function getMonitoringAccess(): Promise<MonitoringAccessDecision> {
  return fetchMonitoringWithAuth<MonitoringAccessDecision>('monitoring/access/')
}

export async function getMonitoringReady(): Promise<MonitoringReadyPayload> {
  return fetchMonitoringWithAuth<MonitoringReadyPayload>('monitoring/ready/')
}

export async function getMonitoringStats(): Promise<MonitoringStatsPayload> {
  return fetchMonitoringWithAuth<MonitoringStatsPayload>('monitoring/stats/')
}
