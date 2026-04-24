'use client'

import { useMemo } from 'react'
import Sidebar from '@/components/Sidebar'
import {
    getMonitoringAccess,
    getMonitoringLive,
    getMonitoringReady,
    getMonitoringStats,
} from '@/services/monitoring'
import {
    MonitoringAccessRequiredSection,
    MonitoringAuthEventsSection,
    MonitoringAuthEventsSkeleton,
    MonitoringHeroSection,
    MonitoringLatencyAndMetersSection,
    MonitoringPanelsSkeleton,
    MonitoringRoutesAndReadinessSection,
    MonitoringRoutesAndReadinessSkeleton,
    MonitoringTrafficSummarySkeleton,
    MonitoringTrafficSummarySection,
} from './components/MonitoringDashboardSections'
import {
    type MonitoringDashboardService,
    useMonitoringDashboardModel,
} from './useMonitoringDashboardModel'

type MonitoringPageProps = {
    readonly monitoringService?: MonitoringDashboardService
}

const defaultMonitoringService: MonitoringDashboardService = {
    getMonitoringLive,
    getMonitoringAccess,
    getMonitoringReady,
    getMonitoringStats,
}

export default function MonitoringPage({ monitoringService = defaultMonitoringService }: MonitoringPageProps) {
    const {
        livePayload,
        accessDecision,
        readyPayload,
        statsPayload,
        isLoading,
        isRefreshing,
        errorMessage,
        consecutiveFailures,
        retryInSeconds,
        isDataStale,
        lastSync,
        hasRealtimeSeries,
        realtimeWindowSeconds,
        realtimeBucketSeconds,
        realtimeTotals,
        eventRows,
        maxEventCount,
        maxRouteRequests,
        latencySeries,
        latencyChart,
        errorRateMeter,
        readinessMeter,
        refreshDashboard,
    } = useMonitoringDashboardModel({ monitoringService })
    const hasMonitoringAccess = Boolean(accessDecision?.allowed)

    const statusAnnouncement = useMemo(() => {
        if (isLoading) {
            return 'Loading monitoring dashboard.'
        }
        if (isRefreshing) {
            return 'Refreshing monitoring metrics.'
        }
        if (errorMessage && retryInSeconds > 0) {
            return `Monitoring refresh failed. Retrying in ${retryInSeconds} seconds.`
        }
        if (errorMessage) {
            return `Monitoring refresh failed. ${errorMessage}`
        }
        if (isDataStale) {
            return 'Monitoring data is stale.'
        }
        if (lastSync) {
            return `Monitoring data updated at ${lastSync}.`
        }
        return 'Monitoring dashboard ready.'
    }, [errorMessage, isDataStale, isLoading, isRefreshing, lastSync, retryInSeconds])

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="monitoring" />
            <main className="ml-56 flex-1 bg-gray-50 px-4 py-8 sm:px-6 lg:px-10">
                <div className="mx-auto max-w-7xl space-y-6">
                    <div className="sr-only" aria-live="polite" aria-atomic="true">
                        {statusAnnouncement}
                    </div>

                    <MonitoringHeroSection
                        lastSync={lastSync}
                        isLoading={isLoading}
                        isRefreshing={isRefreshing}
                        isDataStale={isDataStale}
                        retryInSeconds={retryInSeconds}
                        onRefresh={refreshDashboard}
                    />

                    {errorMessage ? (
                        <div
                            role="alert"
                            className="flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
                        >
                            <span aria-hidden>!</span>
                            <div className="space-y-1">
                                <p>{errorMessage}</p>
                                {retryInSeconds > 0 ? (
                                    <p className="text-xs">
                                        Auto-retry in {retryInSeconds}s (failure streak: {consecutiveFailures}).
                                    </p>
                                ) : null}
                                <button
                                    type="button"
                                    onClick={refreshDashboard}
                                    className="inline-flex items-center rounded-lg border border-red-300 bg-white px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
                                >
                                    Retry Now
                                </button>
                            </div>
                        </div>
                    ) : null}

                    {isLoading ? (
                        <>
                            <MonitoringTrafficSummarySkeleton />
                            <MonitoringPanelsSkeleton />
                            <MonitoringRoutesAndReadinessSkeleton />
                            <MonitoringAuthEventsSkeleton />
                        </>
                    ) : null}

                    {!isLoading && livePayload && accessDecision ? (
                        <>
                            <MonitoringTrafficSummarySection
                                livePayload={livePayload}
                                accessDecision={accessDecision}
                                statsPayload={statsPayload}
                                realtimeTotals={realtimeTotals}
                                hasRealtimeSeries={hasRealtimeSeries}
                                realtimeWindowSeconds={realtimeWindowSeconds}
                            />

                            {hasMonitoringAccess ? (
                                statsPayload ? (
                                    <section className="space-y-4">
                                        <MonitoringLatencyAndMetersSection
                                            latencySeries={latencySeries}
                                            latencyChart={latencyChart}
                                            hasRealtimeSeries={hasRealtimeSeries}
                                            realtimeWindowSeconds={realtimeWindowSeconds}
                                            realtimeBucketSeconds={realtimeBucketSeconds}
                                            errorRateMeter={errorRateMeter}
                                            readinessMeter={readinessMeter}
                                        />
                                        <MonitoringRoutesAndReadinessSection
                                            statsPayload={statsPayload}
                                            maxRouteRequests={maxRouteRequests}
                                            readyPayload={readyPayload}
                                        />
                                        <MonitoringAuthEventsSection
                                            eventRows={eventRows}
                                            maxEventCount={maxEventCount}
                                        />
                                    </section>
                                ) : null
                            ) : (
                                <MonitoringAccessRequiredSection reason={accessDecision.reason} />
                            )}
                        </>
                    ) : null}
                </div>
            </main>
        </div>
    )
}
