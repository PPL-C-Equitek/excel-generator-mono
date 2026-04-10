'use client'

import Sidebar from '@/components/Sidebar'
import { useHistoryFiles } from '@/hooks/useHistoryFiles'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function getDisplayName(customName: string, originalName: string): string {
    return customName.trim() || originalName
}

function getCsvFilename(originalName: string): string {
    return `${originalName.replace(/\.[^.]+$/, '')}.csv`
}

function getXlsxFilename(originalName: string): string {
    return `${originalName.replace(/\.[^.]+$/, '')}.xlsx`
}

function formatCreatedAt(value: string): string {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
        return value
    }

    const day = String(date.getUTCDate()).padStart(2, '0')
    const month = MONTH_LABELS[date.getUTCMonth()]
    const year = date.getUTCFullYear()
    const hours = String(date.getUTCHours()).padStart(2, '0')
    const minutes = String(date.getUTCMinutes()).padStart(2, '0')

    return `${day} ${month} ${year}, ${hours}:${minutes} UTC`
}

export default function HistoryPage() {
    const {
        items,
        count,
        limit,
        offset,
        isLoading,
        loadError,
        downloadError,
        reloadHistory,
        goToNextPage,
        goToPreviousPage,
        downloadCsv,
        downloadExcel,
    } = useHistoryFiles()

    const hasNextPage = offset + limit < count
    const hasItems = items.length > 0

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="history" />
            <main className="flex-1 bg-gray-50 px-16 py-10">
                <div className="mx-auto max-w-5xl">
                    <div className="mb-8">
                        <h1 className="text-2xl font-bold text-gray-900">History</h1>
                        <p className="mt-2 text-sm text-gray-500">
                            Your generated results are available here for CSV or Excel download.
                        </p>
                    </div>

                    {isLoading ? (
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500">
                            Loading history...
                        </div>
                    ) : null}

                    {!isLoading && loadError ? (
                        <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
                            <p className="text-sm text-red-700">{loadError}</p>
                            <button
                                type="button"
                                className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300"
                                onClick={() => {
                                    void reloadHistory()
                                }}
                            >
                                Retry
                            </button>
                        </div>
                    ) : null}

                    {!isLoading && !loadError && !hasItems ? (
                        <div className="rounded-2xl border border-gray-200 bg-white p-6 text-sm text-gray-500">
                            <h2 className="text-base font-semibold text-gray-900">No history yet</h2>
                            <p className="mt-2">
                                Generate a result first, then it will appear here for download.
                            </p>
                        </div>
                    ) : null}

                    {!isLoading && !loadError && hasItems ? (
                        <div className="space-y-4">
                            {downloadError ? (
                                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                                    {downloadError}
                                </div>
                            ) : null}

                            <div className="flex items-center justify-between">
                                <p className="text-sm text-gray-500">
                                    Showing {offset + 1}-{Math.min(offset + items.length, count)} of {count}
                                </p>
                                <div className="flex items-center gap-3">
                                    <button
                                        type="button"
                                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                                        onClick={() => {
                                            void goToPreviousPage()
                                        }}
                                        disabled={offset === 0}
                                    >
                                        Previous
                                    </button>
                                    <button
                                        type="button"
                                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
                                        onClick={() => {
                                            void goToNextPage()
                                        }}
                                        disabled={!hasNextPage}
                                    >
                                        Next
                                    </button>
                                </div>
                            </div>

                            {items.map((item) => (
                                <section
                                    key={item.id}
                                    className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm"
                                >
                                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                        <div className="space-y-2">
                                            <h2 className="text-lg font-semibold text-gray-900">
                                                {getDisplayName(item.custom_name, item.original_name)}
                                            </h2>
                                            <p className="text-sm text-gray-500">
                                                Original file: {item.original_name}
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                Status: {item.status_processing}
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                Created at: {formatCreatedAt(item.created_at)}
                                            </p>
                                        </div>

                                        <div className="flex flex-col gap-3 sm:flex-row">
                                            <button
                                                type="button"
                                                className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300"
                                                onClick={() => {
                                                    void downloadCsv(
                                                        item.id,
                                                        getCsvFilename(item.original_name)
                                                    )
                                                }}
                                            >
                                                Download CSV
                                            </button>
                                            <button
                                                type="button"
                                                className="rounded-lg border border-red-700 px-4 py-2 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300"
                                                onClick={() => {
                                                    void downloadExcel(
                                                        item.id,
                                                        getXlsxFilename(item.original_name)
                                                    )
                                                }}
                                            >
                                                Download Excel
                                            </button>
                                        </div>
                                    </div>
                                </section>
                            ))}
                        </div>
                    ) : null}
                </div>
            </main>
        </div>
    )
}
