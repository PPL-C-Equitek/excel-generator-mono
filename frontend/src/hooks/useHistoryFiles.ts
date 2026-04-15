'use client'

import { useCallback, useEffect, useState } from 'react'
import {
    deleteHistoryFile,
    downloadHistoryFile,
    getHistoryFiles,
    renameHistoryFile,
    type HistoryItem,
    type HistoryListResponse,
} from '@/services/history'

interface HistoryService {
    getHistoryFiles: (limit?: number, offset?: number) => Promise<HistoryListResponse>
    downloadHistoryFile: (
        historyId: string,
        fileFormat: 'csv' | 'xlsx',
        filename?: string
    ) => Promise<void>
    renameHistoryFile: (historyId: string, customName: string) => Promise<HistoryItem>
    deleteHistoryFile: (historyId: string) => Promise<void>
}

interface UseHistoryFilesReturn {
    items: HistoryItem[]
    count: number
    limit: number
    offset: number
    isLoading: boolean
    renamingHistoryId: string | null
    deletingHistoryId: string | null
    isDownloading: (historyId: string, fileFormat: 'csv' | 'xlsx') => boolean
    downloadError: string | null
    loadError: string | null
    mutationError: string | null
    error: string | null
    reloadHistory: () => Promise<void>
    goToNextPage: () => Promise<void>
    goToPreviousPage: () => Promise<void>
    downloadCsv: (historyId: string, filename?: string) => Promise<void>
    downloadExcel: (historyId: string, filename?: string) => Promise<void>
    renameHistory: (historyId: string, customName: string) => Promise<boolean>
    deleteHistory: (historyId: string) => Promise<boolean>
}

const DEFAULT_LIMIT = 10

const historyService: HistoryService = {
    getHistoryFiles,
    downloadHistoryFile,
    renameHistoryFile,
    deleteHistoryFile,
}

function getErrorMessage(error: unknown, fallback: string): string {
    return error instanceof Error ? error.message : fallback
}

function getDownloadKey(historyId: string, fileFormat: 'csv' | 'xlsx'): string {
    return `${historyId}:${fileFormat}`
}

export function useHistoryFiles(
    service: HistoryService = historyService
): UseHistoryFilesReturn {
    const [items, setItems] = useState<HistoryItem[]>([])
    const [count, setCount] = useState(0)
    const [limit, setLimit] = useState(DEFAULT_LIMIT)
    const [offset, setOffset] = useState(0)
    const [isLoading, setIsLoading] = useState(true)
    const [renamingHistoryId, setRenamingHistoryId] = useState<string | null>(null)
    const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [downloadError, setDownloadError] = useState<string | null>(null)
    const [mutationError, setMutationError] = useState<string | null>(null)
    const [activeDownloads, setActiveDownloads] = useState<Record<string, boolean>>({})

    const loadHistory = useCallback(async (
        nextLimit: number,
        nextOffset: number,
        options?: { showLoader?: boolean }
    ) => {
        const showLoader = options?.showLoader ?? true
        if (showLoader) {
            setIsLoading(true)
        }
        setLoadError(null)

        try {
            const response = await service.getHistoryFiles(nextLimit, nextOffset)
            setItems(response.results)
            setCount(response.count)
            setLimit(response.limit)
            setOffset(response.offset)
        } catch (error: unknown) {
            setItems([])
            setCount(0)
            setLoadError(getErrorMessage(error, 'Failed to load history.'))
        } finally {
            if (showLoader) {
                setIsLoading(false)
            }
        }
    }, [service])

    useEffect(() => {
        void loadHistory(DEFAULT_LIMIT, 0)
    }, [loadHistory])

    const reloadHistory = async () => {
        await loadHistory(limit, offset)
    }

    const goToNextPage = async () => {
        const nextOffset = offset + limit
        if (nextOffset >= count) {
            return
        }

        await loadHistory(limit, nextOffset)
    }

    const goToPreviousPage = async () => {
        if (offset === 0) {
            return
        }

        await loadHistory(limit, Math.max(0, offset - limit))
    }

    const downloadFile = async (
        historyId: string,
        fileFormat: 'csv' | 'xlsx',
        filename?: string
    ) => {
        const downloadKey = getDownloadKey(historyId, fileFormat)
        if (activeDownloads[downloadKey]) {
            return
        }

        setDownloadError(null)
        setActiveDownloads((current) => ({
            ...current,
            [downloadKey]: true,
        }))

        try {
            await service.downloadHistoryFile(historyId, fileFormat, filename)
        } catch (error: unknown) {
            setDownloadError(getErrorMessage(error, 'Failed to download history file.'))
        } finally {
            setActiveDownloads((current) => {
                const next = { ...current }
                delete next[downloadKey]
                return next
            })
        }
    }

    const renameHistory = async (
        historyId: string,
        customName: string
    ): Promise<boolean> => {
        setMutationError(null)
        setRenamingHistoryId(historyId)

        try {
            const updatedHistory = await service.renameHistoryFile(historyId, customName)
            setItems((current) =>
                current.map((item) =>
                    item.id === historyId ? updatedHistory : item
                )
            )
            return true
        } catch (error: unknown) {
            setMutationError(getErrorMessage(error, 'Failed to rename history item.'))
            return false
        } finally {
            setRenamingHistoryId(null)
        }
    }

    const deleteHistory = async (historyId: string): Promise<boolean> => {
        setMutationError(null)
        setDeletingHistoryId(historyId)

        try {
            await service.deleteHistoryFile(historyId)
            const nextCount = Math.max(0, count - 1)
            const remainingItems = items.filter((item) => item.id !== historyId)
            const shouldLoadPreviousPage = nextCount > 0 && offset >= nextCount
            const shouldRefillCurrentPage =
                nextCount > offset + remainingItems.length

            if (shouldLoadPreviousPage) {
                await loadHistory(limit, Math.max(0, offset - limit), { showLoader: false })
            } else if (shouldRefillCurrentPage) {
                await loadHistory(limit, offset, { showLoader: false })
            } else {
                setItems(remainingItems)
                setCount(nextCount)
            }

            return true
        } catch (error: unknown) {
            setMutationError(getErrorMessage(error, 'Failed to delete history item.'))
            return false
        } finally {
            setDeletingHistoryId(null)
        }
    }

    const downloadCsv = async (historyId: string, filename?: string) => {
        await downloadFile(historyId, 'csv', filename)
    }

    const downloadExcel = async (historyId: string, filename?: string) => {
        await downloadFile(historyId, 'xlsx', filename)
    }

    const isDownloading = (historyId: string, fileFormat: 'csv' | 'xlsx') =>
        !!activeDownloads[getDownloadKey(historyId, fileFormat)]

    return {
        items,
        count,
        limit,
        offset,
        isLoading,
        renamingHistoryId,
        deletingHistoryId,
        isDownloading,
        downloadError,
        loadError,
        mutationError,
        error: loadError ?? downloadError ?? mutationError,
        reloadHistory,
        goToNextPage,
        goToPreviousPage,
        downloadCsv,
        downloadExcel,
        renameHistory,
        deleteHistory,
    }
}
