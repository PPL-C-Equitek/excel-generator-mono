import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSessionThinkingLogs } from '../../src/hooks/useSessionThinkingLogs'
import { getThinkingLogsBySession } from '../../src/services/thinkingLogs'
import type { ThinkingLogListResponse } from '../../src/services/thinkingLogs'

vi.mock('../../src/services/thinkingLogs', () => ({
    getThinkingLogsBySession: vi.fn(),
}))

const mockGetThinkingLogsBySession = vi.mocked(getThinkingLogsBySession)

describe('useSessionThinkingLogs', () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    it('keeps an empty state when sessionId is null', () => {
        const { result } = renderHook(() => useSessionThinkingLogs(null))

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.thinkingLogsByOutputId).toEqual({})
        expect(result.current.isLoading).toBe(false)
        expect(result.current.error).toBeNull()
        expect(mockGetThinkingLogsBySession).not.toHaveBeenCalled()
    })

    it('loads thinking logs and indexes them by output id', async () => {
        mockGetThinkingLogsBySession.mockResolvedValue({
            count: 1,
            page: 1,
            page_size: 20,
            results: [
                {
                    id: 'output-1',
                    session_id: 'session-1',
                    chat_id: null,
                    thinking_log: 'Langkah 1',
                    reasoning: ['step1'],
                    status_processing: 'completed',
                    created_at: '2026-04-10T10:01:00Z',
                },
            ],
        })

        const { result } = renderHook(() => useSessionThinkingLogs('session-1'))

        await waitFor(() => expect(mockGetThinkingLogsBySession).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.thinkingLogs).toHaveLength(1))

        expect(result.current.thinkingLogsByOutputId['output-1']).toMatchObject({
            id: 'output-1',
            thinking_log: 'Langkah 1',
        })
        expect(result.current.error).toBeNull()
    })

    it('stores an error when loading thinking logs fails', async () => {
        mockGetThinkingLogsBySession.mockRejectedValue(new Error('Failed to load thinking log.'))

        const { result } = renderHook(() => useSessionThinkingLogs('session-1'))

        await waitFor(() => expect(mockGetThinkingLogsBySession).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.error).toBe('Failed to load thinking log.'))

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.thinkingLogsByOutputId).toEqual({})
    })

    it('stores fallback error when loading fails with non-Error value', async () => {
        mockGetThinkingLogsBySession.mockRejectedValue('failed')

        const { result } = renderHook(() => useSessionThinkingLogs('session-1'))

        await waitFor(() => expect(mockGetThinkingLogsBySession).toHaveBeenCalledWith('session-1'))
        await waitFor(() => expect(result.current.error).toBe('Failed to load thinking log.'))

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.thinkingLogsByOutputId).toEqual({})
    })

    it('does not update state when unmounted before request resolves', async () => {
        vi.useFakeTimers()
        let resolveThinkingLogs: ((value: ThinkingLogListResponse) => void) | null = null
        mockGetThinkingLogsBySession.mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolveThinkingLogs = resolve
                })
        )

        const { result, unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
        await act(async () => {
            await vi.runAllTimersAsync()
        })
        unmount()

        await act(async () => {
            resolveThinkingLogs?.({
                count: 1,
                page: 1,
                page_size: 20,
                results: [
                    {
                        id: 'output-1',
                        session_id: 'session-1',
                        chat_id: null,
                        thinking_log: 'late',
                        reasoning: [],
                        status_processing: 'completed',
                        created_at: '2026-04-10T10:01:00Z',
                    },
                ],
            })
            await Promise.resolve()
        })

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.error).toBeNull()
        vi.useRealTimers()
    })

    it('does not update state when unmounted before request rejects', async () => {
        vi.useFakeTimers()
        let rejectThinkingLogs: ((reason: unknown) => void) | null = null
        mockGetThinkingLogsBySession.mockImplementation(
            () =>
                new Promise((_, reject) => {
                    rejectThinkingLogs = reject
                })
        )

        const { result, unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
        await act(async () => {
            await vi.runAllTimersAsync()
        })
        unmount()

        await act(async () => {
            rejectThinkingLogs?.(new Error('late failure'))
            await Promise.resolve()
        })

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.error).toBeNull()
        vi.useRealTimers()
    })

    it('clears timeout when unmounting before request starts', () => {
        mockGetThinkingLogsBySession.mockResolvedValue({
            count: 0,
            page: 1,
            page_size: 20,
            results: [],
        })
        const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout')

        const { unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
        unmount()

        expect(clearTimeoutSpy).toHaveBeenCalled()
        clearTimeoutSpy.mockRestore()
    })

    it('ignores scheduled callback when timeout runs after unmount', () => {
        mockGetThinkingLogsBySession.mockResolvedValue({
            count: 0,
            page: 1,
            page_size: 20,
            results: [],
        })
        const originalSetTimeout = global.setTimeout
        const originalClearTimeout = global.clearTimeout
        let scheduledCallback: (() => void) | null = null

        vi.stubGlobal('setTimeout', ((callback: TimerHandler) => {
            scheduledCallback = callback as () => void
            return 1
        }) as typeof setTimeout)
        vi.stubGlobal('clearTimeout', vi.fn())

        const { unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
        unmount()
        scheduledCallback?.()

        expect(mockGetThinkingLogsBySession).not.toHaveBeenCalled()

        vi.stubGlobal('setTimeout', originalSetTimeout)
        vi.stubGlobal('clearTimeout', originalClearTimeout)
    })
})
