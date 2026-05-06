type RouteLike = Readonly<{
    route: string
}>

export type MonitoringRouteVisibilityPolicy = Readonly<{
    isSystemRoute: (route: string) => boolean
    shouldShowRoute: (route: string) => boolean
    filterVisibleRoutes: <T extends RouteLike>(routes: readonly T[]) => T[]
}>

const DEFAULT_HIDDEN_ROUTE_PREFIXES = ['monitoring'] as const
type NormalizedRoutePrefix = Readonly<{
    exact: string
    nested: string
}>

function normalizeRoute(route: string): string {
    const trimmedRoute = route.trim()
    let startIndex = 0
    let endIndex = trimmedRoute.length

    // Keep normalization linear for untrusted route strings; avoid regex backtracking entirely.
    while (startIndex < endIndex && trimmedRoute[startIndex] === '/') {
        startIndex += 1
    }

    while (endIndex > startIndex && trimmedRoute[endIndex - 1] === '/') {
        endIndex -= 1
    }

    return trimmedRoute.slice(startIndex, endIndex).toLowerCase()
}

function routeMatchesPrefix(normalizedRoute: string, prefix: NormalizedRoutePrefix): boolean {
    return normalizedRoute === prefix.exact || normalizedRoute.startsWith(prefix.nested)
}

export function createMonitoringRouteVisibilityPolicy(
    hiddenRoutePrefixes: readonly string[] = DEFAULT_HIDDEN_ROUTE_PREFIXES,
): MonitoringRouteVisibilityPolicy {
    const normalizedHiddenRoutePrefixes = hiddenRoutePrefixes.map((prefix) => {
        const normalizedPrefix = normalizeRoute(prefix)
        return {
            exact: normalizedPrefix,
            nested: `${normalizedPrefix}/`,
        }
    })

    const isSystemRoute = (route: string): boolean => {
        const normalizedRoute = normalizeRoute(route)

        return normalizedHiddenRoutePrefixes.some((prefix) => routeMatchesPrefix(normalizedRoute, prefix))
    }

    const shouldShowRoute = (route: string): boolean => !isSystemRoute(route)

    return {
        isSystemRoute,
        shouldShowRoute,
        filterVisibleRoutes: (routes) => routes.filter((routeRow) => shouldShowRoute(routeRow.route)),
    }
}

export const monitoringRouteVisibilityPolicy = createMonitoringRouteVisibilityPolicy()
