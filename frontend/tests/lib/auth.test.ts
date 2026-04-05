import { afterEach, describe, expect, it, vi } from 'vitest'
import {
    clearAuthTokens,
    getStoredAccessToken,
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

    it('returns null when neither storage contains a usable token', () => {
        expect(getStoredAccessToken()).toBeNull()
    })

    it('reads the new snake_case access token key', () => {
        window.localStorage.setItem('access_token', 'snake-token')

        expect(getStoredAccessToken()).toBe('snake-token')
    })

    it('reads the new snake_case refresh token key', async () => {
        window.localStorage.setItem('refresh_token', 'snake-refresh')

        const { getStoredRefreshToken } = await import('@/lib/auth')

        expect(getStoredRefreshToken()).toBe('snake-refresh')
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

        clearAuthTokens()

        expect(window.localStorage.getItem('access_token')).toBeNull()
        expect(window.localStorage.getItem('refresh_token')).toBeNull()
        expect(window.sessionStorage.getItem('access_token')).toBeNull()
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
})
