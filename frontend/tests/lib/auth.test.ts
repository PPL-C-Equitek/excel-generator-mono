import { afterEach, describe, expect, it, vi } from 'vitest'
import {
    clearAuthTokens,
    getStoredAccessToken,
    getStoredRefreshToken,
    getStoredUser,
    getValidAccessToken,
    refreshAccessToken,
    storeAuthTokens,
} from '@/lib/auth'

function encodeJwtPayload(payload: Record<string, unknown>): string {
    const json = JSON.stringify(payload)
    const base64 = globalThis.btoa(json)
    return base64.replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
}

function makeJwt(payload: Record<string, unknown>): string {
    return `header.${encodeJwtPayload(payload)}.signature`
}

describe('getStoredAccessToken', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    it('returns null when window is unavailable', () => {
        vi.stubGlobal('window', undefined)

        expect(getStoredAccessToken()).toBeNull()
    })

    it('reads the access token from localStorage first', () => {
        window.localStorage.setItem('accessToken', 'local-token')

        expect(getStoredAccessToken()).toBe('local-token')
    })

    it('falls back to sessionStorage when localStorage values are blank', () => {
        window.localStorage.setItem('accessToken', '   ')
        window.sessionStorage.setItem('auth.accessToken', 'session-token')

        expect(getStoredAccessToken()).toBe('session-token')
    })

    it('returns null when storage access throws', () => {
        vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
            throw new Error('storage blocked')
        })

        expect(getStoredAccessToken()).toBeNull()
    })

    it('returns null when prototype storage access throws', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('storage blocked')
        })

        expect(getStoredAccessToken()).toBeNull()
    })

    it('returns null when neither storage contains a usable token', () => {
        expect(getStoredAccessToken()).toBeNull()
    })

    it('returns null when sessionStorage access throws after localStorage is blank', () => {
        window.localStorage.setItem('accessToken', '   ')
        vi.spyOn(window.sessionStorage, 'getItem').mockImplementation(() => {
            throw new Error('session storage blocked')
        })

        expect(getStoredAccessToken()).toBeNull()
    })

    it('reads the new snake_case access token key', () => {
        window.localStorage.setItem('access_token', 'snake-token')

        expect(getStoredAccessToken()).toBe('snake-token')
    })

    it('reads the new snake_case refresh token key', async () => {
        window.localStorage.setItem('refresh_token', 'snake-refresh')

        expect(getStoredRefreshToken()).toBe('snake-refresh')
    })

    it('returns null for refresh token when window is unavailable', () => {
        vi.stubGlobal('window', undefined)

        expect(getStoredRefreshToken()).toBeNull()
    })

    it('reads refresh token from sessionStorage when localStorage is blank', () => {
        window.localStorage.setItem('refresh_token', '   ')
        window.sessionStorage.setItem('auth.refreshToken', 'session-refresh')

        expect(getStoredRefreshToken()).toBe('session-refresh')
    })

    it('returns null when refresh token storage access throws', () => {
        vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
            throw new Error('storage blocked')
        })

        expect(getStoredRefreshToken()).toBeNull()
    })

    it('returns null when prototype refresh token storage access throws', () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('storage blocked')
        })

        expect(getStoredRefreshToken()).toBeNull()
    })
})

describe('auth token refresh helpers', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    it('stores access and refresh tokens in localStorage and sessionStorage', () => {
        storeAuthTokens('access-token', 'refresh-token')

        expect(window.localStorage.getItem('access_token')).toBe('access-token')
        expect(window.localStorage.getItem('refresh_token')).toBe('refresh-token')
        expect(window.sessionStorage.getItem('access_token')).toBe('access-token')
    })

    it('clears stored auth tokens from both storages', () => {
        storeAuthTokens('access-token', 'refresh-token')
        window.localStorage.setItem('user_name', 'Stored Name')
        window.localStorage.setItem('user_email', 'stored@example.com')

        clearAuthTokens()

        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
        expect(window.sessionStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('user_name')).toBeNull()
        expect(window.localStorage.getItem('user_email')).toBeNull()
    })

    it('returns current access token when it is still valid', async () => {
        const futureExp = Math.floor(Date.now() / 1000) + 3600
        const accessToken = makeJwt({ exp: futureExp })

        storeAuthTokens(accessToken, 'refresh-token')

        const mockedFetch = vi.fn()
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe(accessToken)
        expect(mockedFetch).not.toHaveBeenCalled()
    })

    it('refreshes expired access token and stores the new pair', async () => {
        const expiredExp = Math.floor(Date.now() / 1000) - 10
        const expiredAccessToken = makeJwt({ exp: expiredExp })
        const refreshedAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })

        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: refreshedAccessToken,
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe(refreshedAccessToken)

        expect(mockedFetch).toHaveBeenCalledWith(
            expect.stringContaining('/auth/refresh/'),
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
        )
        expect(window.localStorage.getItem('access_token')).toBe(refreshedAccessToken)
        expect(window.localStorage.getItem('refresh_token')).toBe('new-refresh-token')
    })

    it('returns null and clears tokens when refresh fails', async () => {
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            json: async () => ({ message: 'Token expired' }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(refreshAccessToken()).resolves.toBeNull()
        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
    })

    it('returns null when no refresh token is stored', async () => {
        const mockedFetch = vi.fn()
        vi.stubGlobal('fetch', mockedFetch)

        await expect(refreshAccessToken()).resolves.toBeNull()
        expect(mockedFetch).not.toHaveBeenCalled()
    })

    it('returns null when refresh request throws (network error)', async () => {
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockRejectedValue(new TypeError('Network down'))
        vi.stubGlobal('fetch', mockedFetch)

        await expect(refreshAccessToken()).resolves.toBeNull()
        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
    })

    it('returns null when refresh response is malformed', async () => {
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ access_token: 'only-access-token' }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(refreshAccessToken()).resolves.toBeNull()
        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
    })

    it('returns null when refresh response JSON parsing throws', async () => {
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => {
                throw new Error('invalid json')
            },
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(refreshAccessToken()).resolves.toBeNull()
        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
    })

    it('refreshes expired access token when getValidAccessToken sees an expired JWT', async () => {
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })
        const refreshedAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })

        storeAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: refreshedAccessToken,
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe(refreshedAccessToken)
        expect(window.localStorage.getItem('access_token')).toBe(refreshedAccessToken)
        expect(window.localStorage.getItem('refresh_token')).toBe('new-refresh-token')
    })

    it('returns null when access token payload is not decodable', async () => {
        window.localStorage.setItem('access_token', 'not-a-jwt')
        window.localStorage.setItem('refresh_token', 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: 'still-bad',
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe('still-bad')
        expect(mockedFetch).toHaveBeenCalled()
    })

    it('returns null from refreshAccessToken when window is unavailable', async () => {
        vi.stubGlobal('window', undefined)

        await expect(refreshAccessToken()).resolves.toBeNull()
    })

    it('returns null from getValidAccessToken when window is unavailable', async () => {
        vi.stubGlobal('window', undefined)

        await expect(getValidAccessToken()).resolves.toBeNull()
    })

    it('tries refresh flow when there is no access token', async () => {
        const refreshedAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
        window.localStorage.setItem('refresh_token', 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: refreshedAccessToken,
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe(refreshedAccessToken)
        expect(mockedFetch).toHaveBeenCalledTimes(1)
    })

    it('does not throw when storing tokens and window is unavailable', () => {
        vi.stubGlobal('window', undefined)

        expect(() => storeAuthTokens('access', 'refresh')).not.toThrow()
    })

    it('does not throw when storage setItem throws during storeAuthTokens', () => {
        vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
            throw new Error('write blocked')
        })

        expect(() => storeAuthTokens('access', 'refresh')).not.toThrow()
    })

    it('does not throw when clearing tokens and window is unavailable', () => {
        vi.stubGlobal('window', undefined)

        expect(() => clearAuthTokens()).not.toThrow()
    })

    it('does not throw when storage removeItem throws during clearAuthTokens', () => {
        vi.spyOn(window.localStorage, 'removeItem').mockImplementation(() => {
            throw new Error('remove blocked')
        })

        expect(() => clearAuthTokens()).not.toThrow()
    })

    it('handles missing storage objects as no-ops', () => {
        vi.stubGlobal('window', {
            localStorage: undefined,
            sessionStorage: undefined,
        } as unknown as Window)

        expect(getStoredAccessToken()).toBeNull()
        expect(getStoredRefreshToken()).toBeNull()
        expect(() => storeAuthTokens('access', 'refresh')).not.toThrow()
        expect(() => clearAuthTokens()).not.toThrow()
    })

    it('refreshes when access token payload has no exp claim', async () => {
        const accessTokenWithoutExp = makeJwt({ user_id: 'no-exp', email: 'no-exp@example.com' })
        const refreshedAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })

        storeAuthTokens(accessTokenWithoutExp, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: refreshedAccessToken,
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await expect(getValidAccessToken()).resolves.toBe(refreshedAccessToken)
    })

    it('normalizes a trailing slash in NEXT_PUBLIC_API_URL when building the refresh endpoint', async () => {
        vi.resetModules()
        vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://example.com/')

        const { storeAuthTokens: importedStoreAuthTokens, refreshAccessToken: importedRefreshAccessToken } = await import('@/lib/auth')
        const expiredAccessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) - 10 })

        importedStoreAuthTokens(expiredAccessToken, 'refresh-token')

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({
                access_token: makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 }),
                refresh_token: 'new-refresh-token',
            }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        await importedRefreshAccessToken()

        expect(mockedFetch).toHaveBeenCalledWith(
            'https://example.com/auth/refresh/',
            expect.objectContaining({
                method: 'POST',
            })
        )
    })
})

describe('getStoredUser', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    it('returns null when window is unavailable', () => {
        vi.stubGlobal('window', undefined)

        expect(getStoredUser()).toBeNull()
    })

    it('returns null when there is no stored access token', () => {
        window.localStorage.setItem('user_name', 'Name Only')

        expect(getStoredUser()).toBeNull()
    })

    it('uses localStorage user_name and user_email when present', () => {
        const accessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
        window.localStorage.setItem('access_token', accessToken)
        window.localStorage.setItem('user_name', 'Stored Name')
        window.localStorage.setItem('user_email', 'stored@example.com')

        expect(getStoredUser()).toEqual({
            id: '',
            email: 'stored@example.com',
            name: 'Stored Name',
        })
    })

    it('uses stored user name when email metadata is missing', () => {
        const accessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
        window.localStorage.setItem('access_token', accessToken)
        window.localStorage.setItem('user_name', 'Name Only')

        expect(getStoredUser()).toEqual({
            id: '',
            email: '',
            name: 'Name Only',
        })
    })

    it('falls back to email when user_name is missing in storage', () => {
        const accessToken = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
        window.localStorage.setItem('access_token', accessToken)
        window.localStorage.setItem('user_email', 'emailonly@example.com')

        expect(getStoredUser()).toEqual({
            id: '',
            email: 'emailonly@example.com',
            name: 'emailonly@example.com',
        })
    })

    it('falls back to JWT payload when storage metadata is absent', () => {
        const accessToken = makeJwt({
            exp: Math.floor(Date.now() / 1000) + 3600,
            user_id: 'user-123',
            email: 'jwt@example.com',
            name: 'JWT Name',
        })
        window.localStorage.setItem('access_token', accessToken)

        expect(getStoredUser()).toEqual({
            id: 'user-123',
            email: 'jwt@example.com',
            name: 'JWT Name',
        })
    })

    it('falls back to JWT email when JWT name is missing', () => {
        const accessToken = makeJwt({
            exp: Math.floor(Date.now() / 1000) + 3600,
            user_id: 'user-456',
            email: 'jwt-email@example.com',
        })
        window.localStorage.setItem('access_token', accessToken)

        expect(getStoredUser()).toEqual({
            id: 'user-456',
            email: 'jwt-email@example.com',
            name: 'jwt-email@example.com',
        })
    })

    it('falls back to a default user name when JWT payload has no name or email', () => {
        const accessToken = makeJwt({
            exp: Math.floor(Date.now() / 1000) + 3600,
            user_id: 'user-789',
        })
        window.localStorage.setItem('access_token', accessToken)

        expect(getStoredUser()).toEqual({
            id: 'user-789',
            email: undefined,
            name: 'User',
        })
    })

    it('returns null when JWT payload is not decodable', () => {
        window.localStorage.setItem('access_token', 'header.invalid-base64.signature')

        expect(getStoredUser()).toBeNull()
    })

    it('returns null when JWT payload JSON is malformed', () => {
        const malformedJsonPayload = globalThis.btoa('{"broken":')
            .replace(/=/g, '')
            .replace(/\+/g, '-')
            .replace(/\//g, '_')

        window.localStorage.setItem('access_token', `header.${malformedJsonPayload}.signature`)

        expect(getStoredUser()).toBeNull()
    })
})
