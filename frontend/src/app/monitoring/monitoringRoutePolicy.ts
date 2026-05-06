type RouteLike = Readonly<{
    route: string
}>

export type MonitoringRouteVisibilityPolicy = Readonly<{
    isSystemRoute: (route: string) => boolean
    shouldShowRoute: (route: string) => boolean
    filterVisibleRoutes: <T extends RouteLike>(routes: readonly T[]) => T[]
}>

const DEFAULT_HIDDEN_ROUTE_PREFIXES = ['monitoring'] as const

function normalizeRoute(route: string): string {
    return route.trim().replace(/^\/+/, '').replace(/\/+$/, '').toLowerCase()
}

function routeMatchesPrefix(route: string, prefix: string): boolean {
    const normalizedRoute = normalizeRoute(route)
    const normalizedPrefix = normalizeRoute(prefix)

    return normalizedRoute === normalizedPrefix || normalizedRoute.startsWith(`${normalizedPrefix}/`)
}

export function createMonitoringRouteVisibilityPolicy(
    hiddenRoutePrefixes: readonly string[] = DEFAULT_HIDDEN_ROUTE_PREFIXES,
): MonitoringRouteVisibilityPolicy {
    const isSystemRoute = (route: string): boolean => (
        hiddenRoutePrefixes.some((prefix) => routeMatchesPrefix(route, prefix))
    )

    const shouldShowRoute = (route: string): boolean => !isSystemRoute(route)

    return {
        isSystemRoute,
        shouldShowRoute,
        filterVisibleRoutes: (routes) => routes.filter((routeRow) => shouldShowRoute(routeRow.route)),
    }
}

export const monitoringRouteVisibilityPolicy = createMonitoringRouteVisibilityPolicy()
