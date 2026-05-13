import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type {
    MonitoringAccessDecision,
    MonitoringAuthenticatedSnapshot,
    MonitoringLivePayload,
    MonitoringReadyPayload,
    MonitoringStatsPayload,
    MonitoringStatsStreamHandle,
    MonitoringStatsStreamOptions,
} from '@/services/monitoring'
import { getMonitoringAuthToken, MONITORING_STREAM_UNEXPECTED_CLOSE_MESSAGE } from '@/services/monitoring'
import {
    createMonitoringDashboardProjection,
    type MonitoringDashboardProjection,
} from './monitoringDashboardProjection'

const DEFAULT_AUTO_REFRESH_INTERVAL_MS = 5000
const STALE_THRESHOLD_MULTIPLIER = 3
const MIN_STALE_THRESHOLD_MS = 15000
const RETRY_BASE_DELAY_MS = 2000
const RETRY_MAX_DELAY_MS = 30000
const RETRY_TICK_INTERVAL_MS = 1000

export type MonitoringDashboardService = {
    getMonitoringLive: () => Promise<MonitoringLivePayload>
    getMonitoringAccess: (accessToken?: string) => Promise<MonitoringAccessDecision>
    getMonitoringReady: (accessToken?: string) => Promise<MonitoringReadyPayload>
    getMonitoringStats: (accessToken?: string) => Promise<MonitoringStatsPayload>
    getMonitoringStatsStream?: (options: MonitoringStatsStreamOptions) => Promise<MonitoringStatsStreamHandle>
    getMonitoringAuthenticatedSnapshot?: () => Promise<MonitoringAuthenticatedSnapshot>
}

export type MonitoringDashboardViewModel = MonitoringDashboardProjection & {
    livePayload: MonitoringLivePayload | null
    accessDecision: MonitoringAccessDecision | null
    readyPayload: MonitoringReadyPayload | null
    statsPayload: MonitoringStatsPayload | null
    isLoading: boolean
    isRefreshing: boolean
    errorMessage: string | null
    consecutiveFailures: number
    retryInSeconds: number
    nextRetryAtMs: number | null
    isDataStale: boolean
    lastSync: string
    refreshDashboard: () => void
}

type UseMonitoringDashboardModelParams = Readonly<{
    monitoringService: MonitoringDashboardService
    autoRefreshIntervalMs?: number
}>

function calculateRetryDelayMs(consecutiveFailures: number): number {
    return Math.min(
        RETRY_MAX_DELAY_MS,
        RETRY_BASE_DELAY_MS * (2 ** Math.max(0, consecutiveFailures - 1))
    )
}

export function getIsPageVisible(): boolean {
    const pageDocument = globalThis.document
    if (!pageDocument) {
        return true
    }
    return pageDocument.visibilityState === 'visible'
}

export function useMonitoringDashboardModel({
    monitoringService,
    autoRefreshIntervalMs = DEFAULT_AUTO_REFRESH_INTERVAL_MS,
}: UseMonitoringDashboardModelParams): MonitoringDashboardViewModel {
    const isDashboardRequestInFlightRef = useRef(false)
    const monitoringStreamRef = useRef<MonitoringStatsStreamHandle | null>(null)
    const consecutiveFailuresRef = useRef(0)
    const isMountedRef = useRef(true)
    const hasBootstrappedSnapshotRef = useRef(false)

    const [livePayload, setLivePayload] = useState<MonitoringLivePayload | null>(null)
    const [accessDecision, setAccessDecision] = useState<MonitoringAccessDecision | null>(null)
    const [readyPayload, setReadyPayload] = useState<MonitoringReadyPayload | null>(null)
    const [statsPayload, setStatsPayload] = useState<MonitoringStatsPayload | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [lastSuccessfulAtMs, setLastSuccessfulAtMs] = useState<number | null>(null)
    const [consecutiveFailures, setConsecutiveFailures] = useState(0)
    const [nextRetryAtMs, setNextRetryAtMs] = useState<number | null>(null)
    const [retryClockNowMs, setRetryClockNowMs] = useState(() => Date.now())
    const [isDataStale, setIsDataStale] = useState(false)
    const [isPageVisible, setIsPageVisible] = useState(getIsPageVisible)
    const [hasActiveStatsStream, setHasActiveStatsStream] = useState(false)

    const markSuccessfulLoad = useCallback((completedAtMs: number) => {
        consecutiveFailuresRef.current = 0
        setConsecutiveFailures(0)
        setNextRetryAtMs(null)
        setLastSuccessfulAtMs(completedAtMs)
        setRetryClockNowMs(completedAtMs)
        setIsDataStale(false)
    }, [])

    const stopMonitoringStatsStream = useCallback(() => {
        if (monitoringStreamRef.current) {
            monitoringStreamRef.current.close()
            monitoringStreamRef.current = null
        }
        if (!isMountedRef.current) {
            return
        }
        setHasActiveStatsStream(false)
    }, [])

    const scheduleRetry = useCallback((failedAtMs: number) => {
        consecutiveFailuresRef.current += 1
        const nextFailures = consecutiveFailuresRef.current
        setConsecutiveFailures(nextFailures)
        setNextRetryAtMs(failedAtMs + calculateRetryDelayMs(nextFailures))
        setRetryClockNowMs(failedAtMs)
    }, [])

    const loadWithAuthenticatedSnapshot = useCallback(async (
        getMonitoringAuthenticatedSnapshot: NonNullable<MonitoringDashboardService['getMonitoringAuthenticatedSnapshot']>,
    ): Promise<MonitoringAccessDecision> => {
        const [liveResponse, snapshot] = await Promise.all([
            monitoringService.getMonitoringLive(),
            getMonitoringAuthenticatedSnapshot(),
        ])

        if (!isMountedRef.current) {
            return snapshot.accessDecision
        }

        setLivePayload(liveResponse)
        setAccessDecision(snapshot.accessDecision)
        setReadyPayload(snapshot.readyPayload)
        setStatsPayload(snapshot.statsPayload)
        stopMonitoringStatsStream()
        markSuccessfulLoad(Date.now())
        return snapshot.accessDecision
    }, [markSuccessfulLoad, monitoringService, stopMonitoringStatsStream])

    const loadWithoutSnapshot = useCallback(async () => {
        const monitoringAuthToken = await getMonitoringAuthToken()
        const [liveResponse, accessResponse] = await Promise.all([
            monitoringService.getMonitoringLive(),
            monitoringService.getMonitoringAccess(monitoringAuthToken),
        ])

        if (!isMountedRef.current) {
            return ''
        }

        setLivePayload(liveResponse)
        setAccessDecision(accessResponse)

        if (!accessResponse.allowed) {
            setReadyPayload(null)
            setStatsPayload(null)
            stopMonitoringStatsStream()
            markSuccessfulLoad(Date.now())
            return ''
        }

        const readyResponse = await monitoringService.getMonitoringReady(monitoringAuthToken)
        if (!isMountedRef.current) {
            return ''
        }

        setReadyPayload(readyResponse)

        return monitoringAuthToken
    }, [markSuccessfulLoad, monitoringService, stopMonitoringStatsStream])

    const startMonitoringStatsStream = useCallback(async (
        monitoringAuthToken: string,
        getMonitoringStatsStream: NonNullable<MonitoringDashboardService['getMonitoringStatsStream']>,
    ) => {
        const streamPayloads = await getMonitoringStatsStream({
            accessToken: monitoringAuthToken,
            intervalSeconds: autoRefreshIntervalMs / 1000,
            onPayload: (payload) => {
                if (!isMountedRef.current) {
                    return
                }
                setStatsPayload(payload)
                markSuccessfulLoad(Date.now())
            },
            onError: (error) => {
                if (!isMountedRef.current) {
                    return
                }
                const isUnexpectedStreamClose = error.message === MONITORING_STREAM_UNEXPECTED_CLOSE_MESSAGE
                setErrorMessage(isUnexpectedStreamClose ? null : error.message)
                stopMonitoringStatsStream()
                scheduleRetry(Date.now())
            },
        })
        if (!isMountedRef.current) {
            streamPayloads.close()
            return
        }
        monitoringStreamRef.current = streamPayloads
        setHasActiveStatsStream(true)
    }, [autoRefreshIntervalMs, markSuccessfulLoad, scheduleRetry, stopMonitoringStatsStream])

    const loadMonitoringStatsSnapshot = useCallback(async (monitoringAuthToken: string) => {
        const statsResponse = await monitoringService.getMonitoringStats(monitoringAuthToken)
        if (!isMountedRef.current) {
            return
        }

        setStatsPayload(statsResponse)
    }, [monitoringService])

    const setLoadingStateForRequest = useCallback((isBackgroundRefresh: boolean) => {
        if (isBackgroundRefresh) {
            setIsRefreshing(true)
            return
        }
        setIsLoading(true)
    }, [])

    const tryBootstrapWithSnapshot = useCallback(async (isBackgroundRefresh: boolean): Promise<boolean> => {
        const getMonitoringAuthenticatedSnapshot = monitoringService.getMonitoringAuthenticatedSnapshot
        const shouldBootstrapWithSnapshot = !isBackgroundRefresh
            && !hasBootstrappedSnapshotRef.current
            && getMonitoringAuthenticatedSnapshot !== undefined
        if (!shouldBootstrapWithSnapshot) {
            return false
        }

        const accessFromSnapshot = await loadWithAuthenticatedSnapshot(getMonitoringAuthenticatedSnapshot)
        hasBootstrappedSnapshotRef.current = true
        if (!isMountedRef.current) {
            return true
        }
        if (!accessFromSnapshot.allowed) {
            return true
        }

        const getMonitoringStatsStream = monitoringService.getMonitoringStatsStream
        if (getMonitoringStatsStream !== undefined && monitoringStreamRef.current === null) {
            const monitoringAuthToken = await getMonitoringAuthToken()
            await startMonitoringStatsStream(
                monitoringAuthToken,
                getMonitoringStatsStream
            )
        }
        return true
    }, [loadWithAuthenticatedSnapshot, monitoringService, startMonitoringStatsStream])

    const loadStatsForAuthorizedRequest = useCallback(async (monitoringAuthToken: string) => {
        const getMonitoringStatsStream = monitoringService.getMonitoringStatsStream
        const shouldUseStream = getMonitoringStatsStream !== undefined
            && monitoringStreamRef.current === null
        if (shouldUseStream) {
            await startMonitoringStatsStream(
                monitoringAuthToken,
                getMonitoringStatsStream
            )
            return
        }

        if (monitoringStreamRef.current === null) {
            await loadMonitoringStatsSnapshot(monitoringAuthToken)
        }
    }, [loadMonitoringStatsSnapshot, monitoringService, startMonitoringStatsStream])

    const loadDashboard = useCallback(
        async (isBackgroundRefresh: boolean) => {
            if (isDashboardRequestInFlightRef.current) {
                return
            }
            isDashboardRequestInFlightRef.current = true
            setErrorMessage(null)
            setLoadingStateForRequest(isBackgroundRefresh)

            try {
                const bootstrappedWithSnapshot = await tryBootstrapWithSnapshot(isBackgroundRefresh)
                if (bootstrappedWithSnapshot) {
                    return
                }

                const monitoringAuthToken = await loadWithoutSnapshot()
                if (!monitoringAuthToken) {
                    return
                }
                await loadStatsForAuthorizedRequest(monitoringAuthToken)
                if (!isMountedRef.current) {
                    return
                }

                markSuccessfulLoad(Date.now())
            } catch (error) {
                if (!isMountedRef.current) {
                    return
                }

                const failedAtMs = Date.now()
                setReadyPayload(null)
                setStatsPayload(null)
                stopMonitoringStatsStream()
                setErrorMessage(error instanceof Error ? error.message : 'Failed to load monitoring data.')
                scheduleRetry(failedAtMs)
            } finally {
                if (isMountedRef.current) {
                    setIsLoading(false)
                    setIsRefreshing(false)
                }
                isDashboardRequestInFlightRef.current = false
            }
        },
        [
            loadWithoutSnapshot,
            loadStatsForAuthorizedRequest,
            markSuccessfulLoad,
            setLoadingStateForRequest,
            stopMonitoringStatsStream,
            scheduleRetry,
            tryBootstrapWithSnapshot,
        ]
    )

    useEffect(() => {
        void loadDashboard(false)
    }, [loadDashboard])

    useEffect(() => {
        if (!globalThis.document) {
            return
        }
        const visibilityDocument = globalThis.document

        const handleVisibilityChange = () => {
            const nextVisible = getIsPageVisible()
            setIsPageVisible(nextVisible)
            if (!nextVisible) {
                stopMonitoringStatsStream()
            }

            if (nextVisible) {
                void loadDashboard(true)
            }
        }

        visibilityDocument.addEventListener('visibilitychange', handleVisibilityChange)
        return () => {
            visibilityDocument.removeEventListener('visibilitychange', handleVisibilityChange)
        }
    }, [loadDashboard, stopMonitoringStatsStream])

    useEffect(() => {
        if (!isPageVisible || hasActiveStatsStream) {
            return
        }

        const intervalId = globalThis.setInterval(() => {
            const nowMs = Date.now()
            if (nextRetryAtMs !== null && nowMs < nextRetryAtMs) {
                return
            }
            void loadDashboard(true)
        }, autoRefreshIntervalMs)
        return () => {
            globalThis.clearInterval(intervalId)
        }
    }, [autoRefreshIntervalMs, hasActiveStatsStream, isPageVisible, loadDashboard, nextRetryAtMs])

    useEffect(() => {
        if (nextRetryAtMs === null || !isPageVisible) {
            return
        }

        const delayMs = Math.max(0, nextRetryAtMs - Date.now())
        const retryTimeoutId = globalThis.setTimeout(() => {
            void loadDashboard(true)
        }, delayMs)

        return () => {
            globalThis.clearTimeout(retryTimeoutId)
        }
    }, [isPageVisible, loadDashboard, nextRetryAtMs])

    useEffect(() => {
        if (nextRetryAtMs === null) {
            return
        }

        const tick = () => {
            setRetryClockNowMs(Date.now())
        }

        tick()
        const clockId = globalThis.setInterval(tick, RETRY_TICK_INTERVAL_MS)

        return () => {
            globalThis.clearInterval(clockId)
        }
    }, [nextRetryAtMs])

    useEffect(() => {
        isMountedRef.current = true
        return () => {
            isMountedRef.current = false
            stopMonitoringStatsStream()
        }
    }, [stopMonitoringStatsStream])

    const dashboardProjection = useMemo(() => createMonitoringDashboardProjection({
        statsPayload,
        readyPayload,
    }), [readyPayload, statsPayload])

    useEffect(() => {
        if (lastSuccessfulAtMs === null) {
            setIsDataStale(false)
            return
        }

        const staleThresholdMs = Math.max(
            MIN_STALE_THRESHOLD_MS,
            autoRefreshIntervalMs * STALE_THRESHOLD_MULTIPLIER
        )
        const markStaleAtMs = lastSuccessfulAtMs + staleThresholdMs
        const nowMs = Date.now()

        if (nowMs >= markStaleAtMs) {
            setIsDataStale(true)
            return
        }

        setIsDataStale(false)
        const staleTimeoutId = globalThis.setTimeout(() => {
            setIsDataStale(true)
        }, markStaleAtMs - nowMs)

        return () => {
            globalThis.clearTimeout(staleTimeoutId)
        }
    }, [autoRefreshIntervalMs, lastSuccessfulAtMs])

    const retryInSeconds = nextRetryAtMs === null
        ? 0
        : Math.max(0, Math.ceil((nextRetryAtMs - retryClockNowMs) / 1000))

    const lastSync = livePayload?.timestamp ?? statsPayload?.generated_at ?? ''

    const refreshDashboard = useCallback(() => {
        void loadDashboard(true)
    }, [loadDashboard])

    return {
        livePayload,
        accessDecision,
        readyPayload,
        statsPayload,
        isLoading,
        isRefreshing,
        errorMessage,
        consecutiveFailures,
        retryInSeconds,
        nextRetryAtMs,
        isDataStale,
        lastSync,
        ...dashboardProjection,
        refreshDashboard,
    }
}
