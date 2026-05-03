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
        let resolveThinkingLogs: ((value: ThinkingLogListResponse) => void) | null = null
        mockGetThinkingLogsBySession.mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolveThinkingLogs = resolve
                })
        )

        const { result, unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
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
    })

    it('does not update state when unmounted before request rejects', async () => {
        let rejectThinkingLogs: ((reason: unknown) => void) | null = null
        mockGetThinkingLogsBySession.mockImplementation(
            () =>
                new Promise((_, reject) => {
                    rejectThinkingLogs = reject
                })
        )

        const { result, unmount } = renderHook(() => useSessionThinkingLogs('session-1'))
        unmount()

        await act(async () => {
            rejectThinkingLogs?.(new Error('late failure'))
            await Promise.resolve()
        })

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.error).toBeNull()
    })

    it('clears stale logs immediately when the sessionId changes', async () => {
        const firstResponse: ThinkingLogListResponse = {
            count: 1,
            page: 1,
            page_size: 20,
            results: [
                {
                    id: 'output-1',
                    session_id: 'session-1',
                    chat_id: null,
                    thinking_log: 'first',
                    reasoning: [],
                    status_processing: 'completed',
                    created_at: '2026-04-10T10:01:00Z',
                },
            ],
        }
        let resolveSecondRequest: ((value: ThinkingLogListResponse) => void) | null = null

        mockGetThinkingLogsBySession.mockImplementation((sessionId) => {
            if (sessionId === 'session-1') {
                return Promise.resolve(firstResponse)
            }

            return new Promise((resolve) => {
                resolveSecondRequest = resolve
            })
        })

        const { result, rerender } = renderHook(
            ({ currentSessionId }) => useSessionThinkingLogs(currentSessionId),
            { initialProps: { currentSessionId: 'session-1' as string | null } },
        )

        await waitFor(() => expect(result.current.thinkingLogs).toHaveLength(1))

        rerender({ currentSessionId: 'session-2' })

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.isLoading).toBe(true)

        await act(async () => {
            resolveSecondRequest?.({
                count: 1,
                page: 1,
                page_size: 20,
                results: [
                    {
                        id: 'output-2',
                        session_id: 'session-2',
                        chat_id: null,
                        thinking_log: 'second',
                        reasoning: [],
                        status_processing: 'completed',
                        created_at: '2026-04-10T10:02:00Z',
                    },
                ],
            })
            await Promise.resolve()
        })

        await waitFor(() => {
            expect(result.current.thinkingLogs[0]?.id).toBe('output-2')
        })
    })
})
