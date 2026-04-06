import { afterEach, describe, expect, it, vi } from 'vitest'
import { getStoredAccessToken } from '@/lib/auth'

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
})
