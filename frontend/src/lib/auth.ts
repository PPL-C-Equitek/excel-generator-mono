const ACCESS_TOKEN_KEYS = ['accessToken', 'auth.accessToken']

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
    if (typeof window === 'undefined') {
        return null
    }

    return readFromStorage(window.localStorage) ?? readFromStorage(window.sessionStorage)
}
