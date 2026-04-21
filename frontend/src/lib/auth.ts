const ACCESS_TOKEN_KEYS = ['access_token', 'accessToken', 'auth.accessToken']
const REFRESH_TOKEN_KEYS = ['refresh_token', 'refreshToken', 'auth.refreshToken']
const USER_METADATA_KEYS = ['user_name', 'user_email']
export const AUTH_STATE_CHANGE_EVENT = 'app:auth-state-changed'

type TokenPair = {
    access_token: string
    refresh_token: string
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
    .split('')
    .reduceRight((acc, ch) => (acc === '' && ch === '/' ? acc : ch + acc), '')

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

function writeToStorage(storage: Storage | undefined, key: string, value: string) {
    if (!storage) return

    try {
        storage.setItem(key, value)
    } catch {
        // Ignore storage failures so auth checks can still proceed.
    }
}

function removeFromStorage(storage: Storage | undefined, key: string) {
    if (!storage) return

    try {
        storage.removeItem(key)
    } catch {
        // Ignore storage failures so logout cleanup remains best-effort.
    }
}

function emitAuthStateChanged(): void {
    if (globalThis.window === undefined) {
        return
    }

    if (typeof globalThis.window.dispatchEvent !== 'function') {
        return
    }

    globalThis.window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT))
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        const payloadPart = token.split('.')[1]
        if (!payloadPart) {
            return null
        }

        const normalizedPayload = payloadPart
            .replaceAll('-', '+')
            .replaceAll('_', '/');
        const paddedPayload = normalizedPayload.padEnd(
            normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4),
            '='
        )
        const decodedPayload = globalThis.atob(paddedPayload)
        return JSON.parse(decodedPayload) as Record<string, unknown>
    } catch {
        return null
    }
}

function isExpired(token: string): boolean {
    const payload = decodeJwtPayload(token)
    const exp = payload?.exp

    if (typeof exp !== 'number') {
        return true
    }

    return exp <= Math.floor(Date.now() / 1000)
}

function readRefreshTokenFromStorage(storage: Storage | undefined): string | null {
    if (!storage) return null

    for (const key of REFRESH_TOKEN_KEYS) {
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

function buildApiUrl(path: string): string {
    const normalizedPath = path.replace(/^\/+/, '')
    return `${API_URL}/${normalizedPath}`
}

export function getStoredRefreshToken(): string | null {
    if (globalThis.window === undefined) {
        return null
    }

    return (
        readRefreshTokenFromStorage(globalThis.window.localStorage) ??
        readRefreshTokenFromStorage(globalThis.window.sessionStorage)
    )
}

export function storeAuthTokens(accessToken: string, refreshToken: string): void {
    const windowObject = globalThis.window

    writeToStorage(windowObject?.localStorage, 'access_token', accessToken)
    writeToStorage(windowObject?.localStorage, 'accessToken', accessToken)
    writeToStorage(windowObject?.localStorage, 'refresh_token', refreshToken)
    writeToStorage(windowObject?.localStorage, 'refreshToken', refreshToken)
    writeToStorage(windowObject?.sessionStorage, 'access_token', accessToken)
    writeToStorage(windowObject?.sessionStorage, 'refresh_token', refreshToken)
    emitAuthStateChanged()
}

export function clearAuthTokens(options: { emitEvent?: boolean } = {}): void {
    const windowObject = globalThis.window
    const shouldEmitEvent = options.emitEvent ?? true

    for (const key of [...ACCESS_TOKEN_KEYS, ...REFRESH_TOKEN_KEYS, ...USER_METADATA_KEYS]) {
        removeFromStorage(windowObject?.localStorage, key)
        removeFromStorage(windowObject?.sessionStorage, key)
    }

    if (shouldEmitEvent) {
        emitAuthStateChanged()
    }
}

export async function refreshAccessToken(): Promise<string | null> {
    if (globalThis.window === undefined) {
        return null
    }

    const refreshToken = getStoredRefreshToken()
    if (!refreshToken) {
        clearAuthTokens()
        return null
    }

    try {
        const response = await fetch(`${API_URL}/auth/refresh/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
        })

        if (!response.ok) {
            clearAuthTokens()
            return null
        }

        const data = (await response.json()) as Partial<TokenPair>
        if (
            typeof data.access_token !== 'string' ||
            typeof data.refresh_token !== 'string'
        ) {
            clearAuthTokens()
            return null
        }

        storeAuthTokens(data.access_token, data.refresh_token)
        return data.access_token
    } catch {
        clearAuthTokens()
        return null
    }
}

export async function getValidAccessToken(): Promise<string | null> {
    if (globalThis.window === undefined) {
        return null
    }

    const accessToken = getStoredAccessToken()
    if (accessToken && !isExpired(accessToken)) {
        return accessToken
    }

    return refreshAccessToken()
}

export async function hasValidSession(): Promise<boolean> {
    if (globalThis.window === undefined) {
        return false
    }

    const storedAccessToken = getStoredAccessToken()
    const storedRefreshToken = getStoredRefreshToken()

    if (!storedAccessToken || !storedRefreshToken) {
        clearAuthTokens({ emitEvent: false })
        return false
    }

    const accessToken = await getValidAccessToken()
    if (!accessToken) {
        return false
    }

    try {
        const response = await fetch(buildApiUrl('history/?limit=1&offset=0'), {
            method: 'GET',
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        })

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                clearAuthTokens({ emitEvent: false })
            }

            return false
        }

        return true
    } catch {
        return false
    }
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

type StoredUser = {
    id: number | string
    email: string
    name: string
}

export function getStoredUser(): StoredUser | null {
    if (globalThis.window === undefined) return null

    const token = getStoredAccessToken()
    if (!token) return null

    const name = globalThis.window.localStorage.getItem('user_name')
    const email = globalThis.window.localStorage.getItem('user_email')

    if (name || email) {
        const resolvedEmail = email ?? ''
        let resolvedName = 'User'

        if (email) {
            resolvedName = email
        }

        if (name) {
            resolvedName = name
        }

        return {
            id: '',
            email: resolvedEmail,
            name: resolvedName,
        }
    }

    // Fallback ke JWT payload
    const payload = decodeJwtPayload(token)
    if (!payload) return null

    return {
        id: payload.user_id as number,
        email: payload.email as string,
        name: (payload.name ?? payload.email ?? 'User') as string,
    }
}
