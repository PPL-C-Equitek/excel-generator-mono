'use client'

import { useState } from 'react'
import SchemaSelector from '@/components/SchemaSelector'
import Sidebar from '@/components/Sidebar'
import UploadZone from '@/components/UploadZone'
import { useConvertFlow } from '@/hooks/useConvertFlow'
import type { ILLMService } from '@/lib/ILLMService'
import type { CustomSchemaRecord } from '@/lib/ICustomSchemaService'

interface ConvertPageProps {
    readonly llmService?: ILLMService
}

export default function ConvertPage({ llmService: injectedService }: ConvertPageProps) {
    const [selectedSchema, setSelectedSchema] = useState<CustomSchemaRecord | null>(null)
    const {
        isConverting,
        isExcelDownloading,
        canDownloadCsv,
        canDownloadExcel,
        error,
        excelError,
        excelSuccessMessage,
        outputFile,
        thinkingLog,
        handleFileSelect,
        handleCsvDownload,
        handleExcelDownload,
    } = useConvertFlow(injectedService)

    const resultContent = (() => {
        if (isConverting) {
            return (
                <div data-testid="loading-indicator">
                    <p className="font-semibold text-gray-900">Thinking log</p>
                    <div className="mt-3 rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600">
                        <div className="flex items-center gap-2 text-red-700">
                            <div className="h-2 w-2 animate-pulse rounded-full bg-red-700" />
                            <span>Waiting for backend reasoning...</span>
                        </div>
                    </div>
                </div>
            )
        }

        if (error) {
            return (
                <div role="alert" className="flex items-start gap-2 text-red-700">
                    <span aria-hidden>⚠</span>
                    <span>{error}</span>
                </div>
            )
        }

        if (!outputFile) {
            return null
        }

        return (
            <div>
                {thinkingLog && (
                    <div className="mb-4">
                        <p className="font-semibold text-gray-900">Thinking log</p>
                        <div className="mt-3 whitespace-pre-wrap rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
                            {thinkingLog}
                        </div>
                    </div>
                )}

                <p className="font-semibold text-gray-900">Your file is ready.</p>
                <div className="mt-3 rounded-xl border border-gray-200 bg-gray-50 p-3">
                    <p className="break-all font-semibold text-gray-800">{outputFile.filename}</p>
                    <p className="mt-1 text-xs text-gray-500">Format: {outputFile.format}</p>
                    <p className="text-xs text-gray-500" data-testid="file-size">
                        Size: {Math.round(outputFile.size / 1024)} KB
                    </p>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                        {canDownloadCsv && (
                            <button
                                data-testid="download-csv-btn"
                                onClick={() => {
                                    void handleCsvDownload()
                                }}
                                disabled={isConverting}
                                className="rounded-lg bg-red-700 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Download CSV
                            </button>
                        )}

                        {canDownloadExcel && (
                            <button
                                data-testid="download-excel-btn"
                                onClick={() => {
                                    void handleExcelDownload()
                                }}
                                disabled={isConverting || isExcelDownloading}
                                className="rounded-lg border border-red-700 bg-white px-4 py-2 text-xs font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {isExcelDownloading ? 'Downloading Excel...' : 'Download Excel'}
                            </button>
                        )}
                    </div>
                </div>

                {excelSuccessMessage && (
                    <p className="mt-3 text-sm text-green-700">{excelSuccessMessage}</p>
                )}

                {excelError && (
                    <div className="mt-3 flex items-center gap-3">
                        <p className="text-sm text-red-700">{excelError}</p>
                        <button
                            data-testid="retry-excel-btn"
                            onClick={() => {
                                void handleExcelDownload()
                            }}
                            disabled={isConverting || isExcelDownloading}
                            className="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Retry
                        </button>
                    </div>
                )}
            </div>
        )
    })()

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="convert" />
            <main className="ml-56 flex min-h-screen flex-1 justify-center bg-gray-50 px-6 py-8 lg:px-12">
                <div className="w-full max-w-3xl">
                    <UploadZone
                        onFileSelect={(file, prompt) => {
                            void handleFileSelect(file, selectedSchema?.id ?? null, prompt ?? null)
                        }}
                        disabled={isConverting}
                        resultContent={resultContent}
                        footerContent={
                            <SchemaSelector
                                className="mt-0"
                                onSchemaChange={setSelectedSchema}
                            />
                        }
                    />
                </div>
            </main>
        </div>
    )
}
