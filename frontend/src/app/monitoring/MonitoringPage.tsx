'use client'

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
    MonitoringHeroSection,
    MonitoringLatencyAndMetersSection,
    MonitoringRoutesAndReadinessSection,
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

    return (
        <div className="flex min-h-screen bg-gray-50">
            <Sidebar activeMenu="monitoring" />
            <main className="ml-56 flex-1 bg-gray-50 px-4 py-8 sm:px-6 lg:px-10">
                <div className="mx-auto max-w-7xl space-y-6">
                    <MonitoringHeroSection
                        lastSync={lastSync}
                        isLoading={isLoading}
                        isRefreshing={isRefreshing}
                        onRefresh={refreshDashboard}
                    />

                    {errorMessage ? (
                        <div
                            role="alert"
                            className="flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
                        >
                            <span aria-hidden>!</span>
                            <span>{errorMessage}</span>
                        </div>
                    ) : null}

                    {isLoading ? (
                        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-md">
                            <div className="animate-pulse space-y-3">
                                <div className="h-4 w-1/4 rounded bg-gray-200" />
                                <div className="h-4 w-1/2 rounded bg-gray-200" />
                                <div className="h-4 w-3/4 rounded bg-gray-200" />
                            </div>
                        </section>
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

                            {!accessDecision.allowed ? (
                                <MonitoringAccessRequiredSection reason={accessDecision.reason} />
                            ) : null}

                            {accessDecision.allowed && statsPayload ? (
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
                            ) : null}
                        </>
                    ) : null}
                </div>
            </main>
        </div>
    )
}

