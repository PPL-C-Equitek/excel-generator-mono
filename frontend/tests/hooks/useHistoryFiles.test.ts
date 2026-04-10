import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useHistoryFiles } from '../../src/hooks/useHistoryFiles'
import type {
    HistoryItem,
    HistoryListResponse,
} from '../../src/services/history'

interface HistoryServiceMock {
    getHistoryFiles: (limit?: number, offset?: number) => Promise<HistoryListResponse>
    downloadHistoryFile: (
        historyId: string,
        fileFormat: 'csv' | 'xlsx',
        filename?: string
    ) => Promise<void>
}

const historyItems: HistoryItem[] = [
    {
        id: '11111111-1111-1111-1111-111111111111',
        original_name: 'report-a.pdf',
        custom_name: '',
        status_processing: 'completed',
        created_at: '2026-04-10T10:00:00Z',
    },
    {
        id: '22222222-2222-2222-2222-222222222222',
        original_name: 'report-b.pdf',
        custom_name: 'Budget Sheet',
        status_processing: 'completed',
        created_at: '2026-04-10T09:00:00Z',
    },
]

function makeHistoryResponse(
    overrides?: Partial<HistoryListResponse>
): HistoryListResponse {
    return {
        count: historyItems.length,
        limit: 10,
        offset: 0,
        results: historyItems,
        ...overrides,
    }
}

function makeServiceMock(
    overrides?: Partial<HistoryServiceMock>
): HistoryServiceMock {
    return {
        getHistoryFiles: vi.fn().mockResolvedValue(makeHistoryResponse()),
        downloadHistoryFile: vi.fn().mockResolvedValue(undefined),
        ...overrides,
    }
}

describe('useHistoryFiles', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('loads history items on mount', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(service.getHistoryFiles).toHaveBeenCalledWith(10, 0)
        expect(result.current.items).toEqual(historyItems)
        expect(result.current.count).toBe(2)
        expect(result.current.limit).toBe(10)
        expect(result.current.offset).toBe(0)
        expect(result.current.error).toBeNull()
    })

    it('returns an empty history state when the user has no records', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockResolvedValue(
                makeHistoryResponse({
                    count: 0,
                    results: [],
                })
            ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.items).toEqual([])
        expect(result.current.count).toBe(0)
        expect(result.current.error).toBeNull()
    })

    it('stores an error when loading history fails', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockRejectedValue(new Error('Failed to load history.')),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.items).toEqual([])
        expect(result.current.error).toBe('Failed to load history.')
    })

    it('downloads a csv file for a selected history item', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.downloadCsv(historyItems[0].id, 'report-a.csv')
        })

        expect(service.downloadHistoryFile).toHaveBeenCalledWith(
            historyItems[0].id,
            'csv',
            'report-a.csv'
        )
        expect(result.current.downloadError).toBeNull()
    })

    it('downloads an xlsx file for a selected history item', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.downloadExcel(historyItems[1].id, 'report-b.xlsx')
        })

        expect(service.downloadHistoryFile).toHaveBeenCalledWith(
            historyItems[1].id,
            'xlsx',
            'report-b.xlsx'
        )
        expect(result.current.downloadError).toBeNull()
    })

    it('stores a download error when csv download fails', async () => {
        const service = makeServiceMock({
            downloadHistoryFile: vi.fn().mockRejectedValue(new Error('Download failed.')),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.downloadCsv(historyItems[0].id, 'report-a.csv')
        })

        expect(result.current.downloadError).toBe('Download failed.')
    })

    it('reloads the next page of history items', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
        })

        expect(service.getHistoryFiles).toHaveBeenLastCalledWith(10, 10)
        expect(result.current.offset).toBe(10)
    })

    it('does not move to the next page when no more records are available', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValue(makeHistoryResponse({ count: 2, limit: 10, offset: 0 })),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
        })

        expect(service.getHistoryFiles).toHaveBeenCalledTimes(1)
        expect(result.current.offset).toBe(0)
    })

    it('reloads the previous page of history items', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 0 })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 10 })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 0 })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
        })

        await act(async () => {
            await result.current.goToPreviousPage()
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 10, 10)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(3, 10, 0)
        expect(result.current.offset).toBe(0)
    })

    it('does not move to a previous page before offset zero', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToPreviousPage()
        })

        expect(service.getHistoryFiles).toHaveBeenCalledTimes(1)
        expect(result.current.offset).toBe(0)
    })
})
