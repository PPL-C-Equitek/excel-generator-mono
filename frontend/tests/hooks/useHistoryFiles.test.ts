import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useHistoryFiles } from '../../src/hooks/useHistoryFiles'
import * as api from '../../src/lib/api'
import * as auth from '../../src/lib/auth'
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
    renameHistoryFile: (historyId: string, customName: string) => Promise<HistoryItem>
    deleteHistoryFile: (historyId: string) => Promise<void>
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
        renameHistoryFile: vi.fn().mockImplementation(async (historyId: string, customName: string) => {
            const matchingItem = historyItems.find((item) => item.id === historyId)
            if (!matchingItem) {
                throw new Error('History item not found.')
            }

            return {
                ...matchingItem,
                custom_name: customName,
            }
        }),
        deleteHistoryFile: vi.fn().mockResolvedValue(undefined),
        ...overrides,
    }
}

function deferred() {
    let resolve!: () => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<void>((res, rej) => {
        resolve = res
        reject = rej
    })

    return { promise, resolve, reject }
}

describe('useHistoryFiles', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
    })

    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
    })

    it('supports default no-argument signature via built-in service', async () => {
        vi.spyOn(auth, 'getValidAccessToken').mockResolvedValue('access-token')
        const fetchApiSpy = vi.spyOn(api, 'fetchAPI').mockResolvedValue(
            makeHistoryResponse({
                count: 0,
                limit: 10,
                offset: 0,
                results: [],
            })
        )

        const { result } = renderHook(() => useHistoryFiles())

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(fetchApiSpy).toHaveBeenCalledWith('history/?limit=10&offset=0', expect.any(Object))
    })

    it('supports options-only signature via built-in service', async () => {
        vi.spyOn(auth, 'getValidAccessToken').mockResolvedValue('access-token')
        const fetchApiSpy = vi.spyOn(api, 'fetchAPI').mockResolvedValue(
            makeHistoryResponse({
                count: 0,
                limit: 3,
                offset: 0,
                results: [],
            })
        )

        const { result } = renderHook(() => useHistoryFiles({ pageSize: 3 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(fetchApiSpy).toHaveBeenCalledWith('history/?limit=3&offset=0', expect.any(Object))
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

    it('uses fallback message when loading history fails with a non-Error value', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockRejectedValue('fatal'),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.items).toEqual([])
        expect(result.current.error).toBe('Failed to load history.')
    })

    it('loads all history records across multiple pages when loadAll is enabled', async () => {
        const pagedItems = [
            {
                ...historyItems[0],
                id: '33333333-3333-3333-3333-333333333333',
            },
        ]

        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 0,
                        results: [historyItems[0], historyItems[1]],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 2,
                        results: pagedItems,
                    })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service, { loadAll: true, pageSize: 2 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(1, 2, 0)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 2, 2)
        expect(result.current.items).toHaveLength(3)
        expect(result.current.count).toBe(3)
        expect(result.current.limit).toBe(3)
        expect(result.current.offset).toBe(0)
    })

    it('uses safe fallback limit and stops loadAll loop when next page has no results', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 5,
                        limit: 0,
                        offset: 0,
                        results: [historyItems[0], historyItems[1]],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 5,
                        limit: 0,
                        offset: 2,
                        results: [],
                    })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service, { loadAll: true, pageSize: 2 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(1, 2, 0)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 1, 2)
        expect(result.current.items).toHaveLength(2)
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

    it('renames a history item in local state', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.renameHistory(historyItems[0].id, 'Renamed Report')
        })

        expect(service.renameHistoryFile).toHaveBeenCalledWith(
            historyItems[0].id,
            'Renamed Report'
        )
        expect(result.current.items[0].custom_name).toBe('Renamed Report')
        expect(result.current.mutationError).toBeNull()
    })

    it('executes history actions through hook commands', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.commands.downloadCsv(historyItems[0].id, 'report-a.csv').execute()
            await result.current.commands.rename(historyItems[0].id, 'Command Rename').execute()
        })

        await waitFor(() => expect(result.current.items[0].custom_name).toBe('Command Rename'))

        await act(async () => {
            await result.current.commands.delete(historyItems[1].id).execute()
        })

        expect(service.downloadHistoryFile).toHaveBeenCalledWith(
            historyItems[0].id,
            'csv',
            'report-a.csv'
        )
        expect(service.renameHistoryFile).toHaveBeenCalledWith(
            historyItems[0].id,
            'Command Rename'
        )
        expect(service.deleteHistoryFile).toHaveBeenCalledWith(historyItems[1].id)
        expect(result.current.items[0].custom_name).toBe('Command Rename')
    })

    it('stores a mutation error when renaming fails', async () => {
        const service = makeServiceMock({
            renameHistoryFile: vi.fn().mockRejectedValue(new Error('Rename failed.')),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.renameHistory(historyItems[0].id, 'Renamed Report')
        })

        expect(result.current.mutationError).toBe('Rename failed.')
    })

    it('tracks csv download-in-progress and blocks duplicate requests for the same item', async () => {
        const csvDownload = deferred()
        const service = makeServiceMock({
            downloadHistoryFile: vi.fn().mockImplementation(() => csvDownload.promise),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        act(() => {
            void result.current.downloadCsv(historyItems[0].id, 'report-a.csv')
        })

        await waitFor(() =>
            expect(result.current.isDownloading(historyItems[0].id, 'csv')).toBe(true)
        )

        act(() => {
            void result.current.downloadCsv(historyItems[0].id, 'report-a.csv')
        })

        expect(service.downloadHistoryFile).toHaveBeenCalledTimes(1)

        await act(async () => {
            csvDownload.resolve()
            await csvDownload.promise
        })

        expect(result.current.isDownloading(historyItems[0].id, 'csv')).toBe(false)
    })

    it('allows a different download key to proceed while another item is downloading', async () => {
        const firstDownload = deferred()
        const service = makeServiceMock({
            downloadHistoryFile: vi.fn()
                .mockImplementationOnce(() => firstDownload.promise)
                .mockResolvedValueOnce(undefined),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        act(() => {
            void result.current.downloadCsv(historyItems[0].id, 'report-a.csv')
        })

        await waitFor(() =>
            expect(result.current.isDownloading(historyItems[0].id, 'csv')).toBe(true)
        )

        await act(async () => {
            await result.current.downloadExcel(historyItems[0].id, 'report-a.xlsx')
        })

        expect(service.downloadHistoryFile).toHaveBeenCalledTimes(2)
        expect(service.downloadHistoryFile).toHaveBeenNthCalledWith(
            2,
            historyItems[0].id,
            'xlsx',
            'report-a.xlsx'
        )

        await act(async () => {
            firstDownload.resolve()
            await firstDownload.promise
        })
    })

    it('uses the fallback download error message for non-Error failures', async () => {
        const service = makeServiceMock({
            downloadHistoryFile: vi.fn().mockRejectedValue('fatal'),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.downloadExcel(historyItems[1].id, 'report-b.xlsx')
        })

        expect(result.current.downloadError).toBe('Failed to download history file.')
    })

    it('deletes a history item from local state without reloading when the page stays filled', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockResolvedValue(
                makeHistoryResponse({
                    count: 2,
                    results: historyItems,
                })
            ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.deleteHistory(historyItems[0].id)
        })

        expect(service.deleteHistoryFile).toHaveBeenCalledWith(historyItems[0].id)
        expect(service.getHistoryFiles).toHaveBeenCalledTimes(1)
        expect(result.current.items).toHaveLength(1)
        expect(result.current.count).toBe(1)
    })

    it('reloads the current page after delete when more records should refill the page', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 11,
                        limit: 10,
                        offset: 0,
                        results: historyItems,
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 10,
                        limit: 10,
                        offset: 0,
                        results: [historyItems[1]],
                    })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.deleteHistory(historyItems[0].id)
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 10, 0)
    })

    it('reloads the previous page after delete when the current page becomes invalid', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 11,
                        limit: 10,
                        offset: 10,
                        results: [historyItems[0]],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 10,
                        limit: 10,
                        offset: 0,
                        results: historyItems,
                    })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.deleteHistory(historyItems[0].id)
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 10, 0)
    })

    it('stores a mutation error when deleting fails', async () => {
        const service = makeServiceMock({
            deleteHistoryFile: vi.fn().mockRejectedValue(new Error('Delete failed.')),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.deleteHistory(historyItems[0].id)
        })

        expect(result.current.mutationError).toBe('Delete failed.')
    })

    it('reloads the current page of history items', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 0 })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 0 })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.reloadHistory()
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 10, 0)
    })

    it('uses latest response limit when reloading in paged mode', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 5, offset: 0 })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 5, offset: 0 })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.reloadHistory()
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(1, 10, 0)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 5, 0)
    })

    it('uses initial page size when reloading in loadAll mode', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 0,
                        results: [historyItems[0], historyItems[1]],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 2,
                        results: [{
                            ...historyItems[0],
                            id: '33333333-3333-3333-3333-333333333333',
                        }],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 0,
                        results: [historyItems[0], historyItems[1]],
                    })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({
                        count: 3,
                        limit: 2,
                        offset: 2,
                        results: [{
                            ...historyItems[0],
                            id: '44444444-4444-4444-4444-444444444444',
                        }],
                    })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service, { loadAll: true, pageSize: 2 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.reloadHistory()
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(1, 2, 0)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 2, 2)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(3, 2, 0)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(4, 2, 2)
    })

    it('reloads the next page of history items', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi
                .fn()
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 0 })
                )
                .mockResolvedValueOnce(
                    makeHistoryResponse({ count: 25, limit: 10, offset: 10 })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
        })

        expect(service.getHistoryFiles).toHaveBeenLastCalledWith(10, 10)
        expect(result.current.offset).toBe(10)
    })

    it('reloads using the current offset after moving to a later page', async () => {
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
                    makeHistoryResponse({ count: 25, limit: 10, offset: 10 })
                ),
        })
        const { result } = renderHook(() => useHistoryFiles(service))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
        })

        await act(async () => {
            await result.current.reloadHistory()
        })

        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(2, 10, 10)
        expect(service.getHistoryFiles).toHaveBeenNthCalledWith(3, 10, 10)
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

    it('keeps pagination actions as no-op in loadAll mode', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockResolvedValue(
                makeHistoryResponse({
                    count: 2,
                    limit: 2,
                    offset: 0,
                    results: historyItems,
                })
            ),
        })
        const { result } = renderHook(() => useHistoryFiles(service, { loadAll: true, pageSize: 2 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.goToNextPage()
            await result.current.goToPreviousPage()
        })

        expect(service.getHistoryFiles).toHaveBeenCalledTimes(1)
        expect(result.current.offset).toBe(0)
    })

    it('deletes locally without refetching in loadAll mode', async () => {
        const service = makeServiceMock({
            getHistoryFiles: vi.fn().mockResolvedValue(
                makeHistoryResponse({
                    count: 2,
                    limit: 2,
                    offset: 0,
                    results: historyItems,
                })
            ),
        })
        const { result } = renderHook(() => useHistoryFiles(service, { loadAll: true, pageSize: 2 }))

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.deleteHistory(historyItems[0].id)
        })

        expect(service.deleteHistoryFile).toHaveBeenCalledWith(historyItems[0].id)
        expect(service.getHistoryFiles).toHaveBeenCalledTimes(1)
        expect(result.current.items).toEqual([historyItems[1]])
        expect(result.current.count).toBe(1)
    })

    it('does not load history on mount when hook is disabled', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() =>
            useHistoryFiles(service, { enabled: false, pageSize: 10 })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(service.getHistoryFiles).not.toHaveBeenCalled()
        expect(result.current.items).toEqual([])
        expect(result.current.count).toBe(0)
    })

    it('keeps reload and pagination actions as no-op when hook is disabled', async () => {
        const service = makeServiceMock()
        const { result } = renderHook(() =>
            useHistoryFiles(service, { enabled: false, pageSize: 10 })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        await act(async () => {
            await result.current.reloadHistory()
            await result.current.goToNextPage()
            await result.current.goToPreviousPage()
        })

        expect(service.getHistoryFiles).not.toHaveBeenCalled()
        expect(result.current.offset).toBe(0)
    })
})
