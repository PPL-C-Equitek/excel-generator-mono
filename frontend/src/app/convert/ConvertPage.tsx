'use client'

import SchemaSelector from '@/components/SchemaSelector'
import Sidebar from '@/components/Sidebar'
import UploadZone from '@/components/UploadZone'
import { useConvertFlow } from '@/hooks/useConvertFlow'
import type { ILLMService } from '@/lib/ILLMService'

interface ConvertPageProps {
    readonly llmService?: ILLMService
}

function getDownloadFilename(baseFilename: string): string {
    return baseFilename.replace(/\.[^/.]+$/, '') + '.csv'
}

export default function ConvertPage({ llmService: injectedService }: ConvertPageProps) {
    const {
        isConverting,
        error,
        outputFile,
        csvMetadata,
        handleFileSelect,
        llmService,
    } = useConvertFlow(injectedService)

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="convert" />
            <main className="ml-56 flex flex-1 flex-col items-center justify-center bg-gray-50 px-16 py-12">
                <h1 className="mb-3 text-2xl font-bold text-gray-900">
                    Automate Your Data Structuring
                </h1>
                <p className="mb-8 max-w-md text-center text-gray-500">
                    Replace manual entry with AI-driven extraction and seamless Excel template mapping.
                </p>
                <div className="w-full max-w-3xl">
                    <UploadZone onFileSelect={handleFileSelect} disabled={isConverting} />

                    {isConverting && (
                        <output
                            data-testid="loading-indicator"
                            className="mt-6 flex flex-col items-center gap-3 py-8"
                        >
                            <div className="h-8 w-8 animate-spin rounded-full border-4 border-red-700 border-t-transparent" />
                            <p className="text-sm text-gray-500">Converting...</p>
                        </output>
                    )}

                    {error && (
                        <div
                            role="alert"
                            className="mt-4 flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
                        >
                            <span aria-hidden>!</span>
                            <span>{error}</span>
                        </div>
                    )}

                    {outputFile && !error && (
                        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                            <p className="font-semibold text-gray-800">{outputFile.filename}</p>
                            <p className="mt-1 text-sm text-gray-500">Format: {outputFile.format}</p>
                            <p className="text-sm text-gray-500" data-testid="file-size">
                                Size: {Math.round(outputFile.size / 1024)} KB
                            </p>

                            {llmService.getDownloadUrl && (
                                <button
                                    data-testid="download-csv-btn"
                                    onClick={() => {
                                        const outputFilename = getDownloadFilename(outputFile.filename)
                                        const url = llmService.getDownloadUrl!(
                                            csvMetadata!.file_id,
                                            outputFilename
                                        )
                                        const anchor = document.createElement('a')
                                        anchor.href = url
                                        anchor.download = outputFilename
                                        document.body.appendChild(anchor)
                                        anchor.click()
                                        anchor.remove()
                                    }}
                                    disabled={isConverting || !csvMetadata}
                                    className="mt-4 ml-4 rounded-xl bg-green-700 px-6 py-2 font-bold text-white transition hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    Download Output
                                </button>
                            )}
                        </div>
                    )}

                    <SchemaSelector />
                </div>
            </main>
        </div>
    )
}
