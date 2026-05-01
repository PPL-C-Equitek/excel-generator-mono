import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSessionResume } from '../../src/hooks/useSessionResume'
import { getSessionResume } from '../../src/services/sessions'

vi.mock('../../src/services/sessions', () => ({
    getSessionResume: vi.fn(),
}))

const mockGetSessionResume = vi.mocked(getSessionResume)

const sessionResume = {
    id: 'session-1',
    title: 'Resume Session',
    created_at: '2026-04-10T10:00:00Z',
    updated_at: '2026-04-10T10:01:00Z',
    last_message_at: null,
    last_output_at: null,
    history: [],
}

describe('useSessionResume', () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it('keeps an empty state when sessionId is null', () => {
        const { result } = renderHook(() => useSessionResume(null))

        expect(result.current.session).toBeNull()
        expect(result.current.isLoading).toBe(false)
        expect(result.current.error).toBeNull()
        expect(result.current.isNotFound).toBe(false)
        expect(mockGetSessionResume).not.toHaveBeenCalled()
    })

    it('loads a session resume when sessionId is provided', async () => {
        mockGetSessionResume.mockResolvedValue(sessionResume)

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(mockGetSessionResume).toHaveBeenCalledWith('session-1')
        expect(result.current.session).toEqual(sessionResume)
        expect(result.current.error).toBeNull()
        expect(result.current.isNotFound).toBe(false)
    })

    it('marks the session as not found when the service rejects with Not found.', async () => {
        mockGetSessionResume.mockRejectedValue(new Error('Not found.'))

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.session).toBeNull()
        expect(result.current.isNotFound).toBe(true)
        expect(result.current.error).toBeNull()
    })

    it('stores a generic error when the service rejects with another error', async () => {
        mockGetSessionResume.mockRejectedValue(new Error('Server down.'))

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.session).toBeNull()
        expect(result.current.isNotFound).toBe(false)
        expect(result.current.error).toBe('Server down.')
    })
})