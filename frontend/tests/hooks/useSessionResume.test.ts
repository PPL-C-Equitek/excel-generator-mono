import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSessionResume } from '../../src/hooks/useSessionResume'
import { getSessionResume } from '../../src/services/sessions'
import type { SessionResume } from '../../src/services/sessions'

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

        await waitFor(() => expect(mockGetSessionResume).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.session).toEqual(sessionResume))

        expect(result.current.error).toBeNull()
        expect(result.current.isNotFound).toBe(false)
    })

    it('marks the session as not found when the service rejects with Not found.', async () => {
        mockGetSessionResume.mockRejectedValue(new Error('Not found.'))

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(mockGetSessionResume).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.isNotFound).toBe(true))

        expect(result.current.session).toBeNull()
        expect(result.current.error).toBeNull()
    })

    it('stores a generic error when the service rejects with another error', async () => {
        mockGetSessionResume.mockRejectedValue(new Error('Server down.'))

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(mockGetSessionResume).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.error).toBe('Server down.'))

        expect(result.current.session).toBeNull()
        expect(result.current.isNotFound).toBe(false)
    })

    it('stores fallback error when service rejects with non-Error value', async () => {
        mockGetSessionResume.mockRejectedValue('unknown failure')

        const { result } = renderHook(() => useSessionResume('session-1'))

        await waitFor(() => expect(mockGetSessionResume).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.error).toBe('Failed to load session.'))

        expect(result.current.session).toBeNull()
        expect(result.current.isNotFound).toBe(false)
    })

    it('does not set state when component unmounts before request completes', async () => {
        let resolveGetSession: ((value: SessionResume) => void) | null = null
        mockGetSessionResume.mockImplementation(
            () => new Promise((resolve) => {
                resolveGetSession = resolve
            })
        )

        const { unmount, result } = renderHook(() => useSessionResume('session-1'))

        unmount()

        // Now resolve the promise after unmount
        await act(async () => {
            resolveGetSession?.(sessionResume)
            await Promise.resolve()
        })

        // State should not have changed since component was unmounted
        expect(result.current.session).toBeNull()
    })

    it('does not set state when component unmounts during error handling', async () => {
        let rejectGetSession: ((reason: unknown) => void) | null = null
        mockGetSessionResume.mockImplementation(
            () => new Promise((_, reject) => {
                rejectGetSession = reject
            })
        )

        const { unmount, result } = renderHook(() => useSessionResume('session-1'))

        unmount()

        // Now reject the promise after unmount
        await act(async () => {
            rejectGetSession?.(new Error('Server error'))
            await Promise.resolve()
        })

        // Error state should not have been set since component was unmounted
        expect(result.current.error).toBeNull()
        expect(result.current.session).toBeNull()
    })

    it('clears stale session data immediately when the sessionId changes', async () => {
        let resolveFirstRequest: ((value: SessionResume) => void) | null = null
        let resolveSecondRequest: ((value: SessionResume) => void) | null = null

        mockGetSessionResume.mockImplementation((sessionId) => {
            if (sessionId === 'session-1') {
                return new Promise((resolve) => {
                    resolveFirstRequest = resolve
                })
            }

            return new Promise((resolve) => {
                resolveSecondRequest = resolve
            })
        })

        const { result, rerender } = renderHook(
            ({ currentSessionId }) => useSessionResume(currentSessionId),
            { initialProps: { currentSessionId: 'session-1' as string | null } },
        )

        expect(result.current.isLoading).toBe(true)
        expect(result.current.session).toBeNull()

        await act(async () => {
            resolveFirstRequest?.(sessionResume)
            await Promise.resolve()
        })

        await waitFor(() => expect(result.current.session).toEqual(sessionResume))

        rerender({ currentSessionId: 'session-2' })

        expect(result.current.session).toBeNull()
        expect(result.current.isLoading).toBe(true)

        await act(async () => {
            resolveSecondRequest?.({
                ...sessionResume,
                id: 'session-2',
            })
            await Promise.resolve()
        })

        await waitFor(() => {
            expect(result.current.session?.id).toBe('session-2')
        })
    })
})
