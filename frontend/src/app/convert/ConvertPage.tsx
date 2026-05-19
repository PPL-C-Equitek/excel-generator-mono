'use client'

import { useEffect, useMemo, useState } from 'react'
import SchemaSelector from '@/components/SchemaSelector'
import ReasoningProcessPanel from '@/components/ReasoningProcessPanel'
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
        isValidating,
        isGenerating,
        errorPhase,
        isExcelDownloading,
        canDownloadCsv,
        canDownloadExcel,
        error,
        excelError,
        excelSuccessMessage,
        outputFile,
        thinkingLog,
        reasoningSteps = [],
        handleFileSelect,
        resetConversionState,
        handleCsvDownload,
        handleExcelDownload,
    } = useConvertFlow(injectedService)

    const reasoningPlaybackKey = useMemo(() => {
        if (!outputFile || reasoningSteps.length === 0) {
            return null
        }

        return [
            outputFile.filename,
            outputFile.size,
            reasoningSteps.join('\n'),
            thinkingLog ?? '',
        ].join('|')
    }, [outputFile, reasoningSteps, thinkingLog])

    const [reasoningPlayback, setReasoningPlayback] = useState({
        key: null as string | null,
        visibleCount: 0,
        completeKey: null as string | null,
    })
    const visibleReasoningCount = reasoningPlayback.key === reasoningPlaybackKey
        ? reasoningPlayback.visibleCount
        : 0

    useEffect(() => {
        if (!reasoningPlaybackKey || reasoningPlayback.completeKey === reasoningPlaybackKey) {
            return
        }

        const timer = globalThis.setTimeout(() => {
            setReasoningPlayback((current) => {
                if (current.completeKey === reasoningPlaybackKey) {
                    return current
                }

                const currentVisibleCount = current.key === reasoningPlaybackKey
                    ? current.visibleCount
                    : 0

                if (currentVisibleCount < reasoningSteps.length) {
                    return {
                        ...current,
                        key: reasoningPlaybackKey,
                        visibleCount: currentVisibleCount + 1,
                    }
                }

                return {
                    ...current,
                    key: reasoningPlaybackKey,
                    visibleCount: currentVisibleCount,
                    completeKey: reasoningPlaybackKey,
                }
            })
        }, visibleReasoningCount === 0 ? 250 : 700)

        return () => globalThis.clearTimeout(timer)
    }, [
        reasoningPlayback.completeKey,
        reasoningPlaybackKey,
        reasoningSteps.length,
        visibleReasoningCount,
    ])

    const isReasoningPlaybackPending = Boolean(
        reasoningPlaybackKey &&
        reasoningPlayback.completeKey !== reasoningPlaybackKey
    )
    const visibleReasoningSteps = reasoningSteps.slice(0, visibleReasoningCount)

    const resultContent = (() => {
        if (isGenerating) {
            return <ReasoningProcessPanel />
        }

        if (isReasoningPlaybackPending) {
            return <ReasoningProcessPanel steps={visibleReasoningSteps} />
        }

        if (error && errorPhase === 'generating') {
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
            <main className="ml-56 flex min-h-screen flex-1 bg-gray-50">
                <div className="w-full">
                    <UploadZone
                        onFileSelect={(file, prompt) => {
                            void handleFileSelect(file, selectedSchema?.id ?? null, prompt ?? null)
                        }}
                        onFileChange={resetConversionState}
                        disabled={isConverting}
                        resultContent={resultContent}
                        selectedSchemaName={selectedSchema?.name ?? null}
                        isValidating={isValidating}
                        isGenerating={isGenerating}
                        validationError={errorPhase === 'validating' ? error : null}
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
