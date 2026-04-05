const ACCESS_TOKEN_KEYS = ['access_token', 'accessToken', 'auth.accessToken']

function readFromStorage(storage: Storage | undefined): string | null {
    if (!storage) return null

    for (const key of ACCESS_TOKEN_KEYS) {
        try {
            const value = storage.getItem(key)
            if (value && value.trim().length > 0) {
                return value
            }
        } catch {
            return null
        }
    }

    return null
}

export function getStoredAccessToken(): string | null {
    if (globalThis.window === undefined) {
        return null
    }

    return (
        readFromStorage(globalThis.window.localStorage) ??
        readFromStorage(globalThis.window.sessionStorage)
    )
}
