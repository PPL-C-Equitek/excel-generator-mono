'use client'

import { useEffect, useState } from 'react'
import {
    downloadHistoryFile,
    getHistoryFiles,
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
}

interface UseHistoryFilesReturn {
    items: HistoryItem[]
    count: number
    limit: number
    offset: number
    isLoading: boolean
    isDownloading: (historyId: string, fileFormat: 'csv' | 'xlsx') => boolean
    downloadError: string | null
    loadError: string | null
    error: string | null
    reloadHistory: () => Promise<void>
    goToNextPage: () => Promise<void>
    goToPreviousPage: () => Promise<void>
    downloadCsv: (historyId: string, filename?: string) => Promise<void>
    downloadExcel: (historyId: string, filename?: string) => Promise<void>
}

const DEFAULT_LIMIT = 10

const historyService: HistoryService = {
    getHistoryFiles,
    downloadHistoryFile,
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
    const [loadError, setLoadError] = useState<string | null>(null)
    const [downloadError, setDownloadError] = useState<string | null>(null)
    const [activeDownloads, setActiveDownloads] = useState<Record<string, boolean>>({})

    const loadHistory = async (nextLimit = limit, nextOffset = offset) => {
        setIsLoading(true)
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
            setIsLoading(false)
        }
    }

    useEffect(() => {
        void loadHistory(DEFAULT_LIMIT, 0)
    }, [])

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
        isDownloading,
        downloadError,
        loadError,
        error: loadError ?? downloadError,
        reloadHistory,
        goToNextPage,
        goToPreviousPage,
        downloadCsv,
        downloadExcel,
    }
}
