import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSessionThinkingLogs } from '../../src/hooks/useSessionThinkingLogs'
import { getThinkingLogsBySession } from '../../src/services/thinkingLogs'

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

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(mockGetThinkingLogsBySession).toHaveBeenCalledWith('session-1')
        expect(result.current.thinkingLogs).toHaveLength(1)
        expect(result.current.thinkingLogsByOutputId['output-1']).toMatchObject({
            id: 'output-1',
            thinking_log: 'Langkah 1',
        })
        expect(result.current.error).toBeNull()
    })

    it('stores an error when loading thinking logs fails', async () => {
        mockGetThinkingLogsBySession.mockRejectedValue(new Error('Failed to load thinking log.'))

        const { result } = renderHook(() => useSessionThinkingLogs('session-1'))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.thinkingLogs).toEqual([])
        expect(result.current.thinkingLogsByOutputId).toEqual({})
        expect(result.current.error).toBe('Failed to load thinking log.')
    })
})