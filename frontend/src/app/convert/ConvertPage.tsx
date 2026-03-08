'use client'

import Sidebar from '@/components/Sidebar'
import UploadZone from '@/components/UploadZone'
import { useConvertFlow } from '@/hooks/useConvertFlow'
import type { ILLMService } from '@/lib/ILLMService'

interface ConvertPageProps {
    readonly llmService?: ILLMService
}

export default function ConvertPage({ llmService }: ConvertPageProps) {
    const { isConverting, error, outputFile, handleFileSelect } = useConvertFlow(llmService)

    return (
        <div className="flex min-h-screen">
            <Sidebar activeMenu="convert" username="Username" />
            <main className="flex-1 bg-gray-50 flex flex-col items-center justify-center px-16">
                <h1 className="text-2xl font-bold text-gray-900 mb-3">
                    Automate Your Data Structuring
                </h1>
                <p className="text-gray-500 text-center mb-8 max-w-md">
                    Replace manual entry with AI-driven extraction and seamless Excel template mapping.
                </p>
                <div className="w-full max-w-3xl">
                    <UploadZone onFileSelect={handleFileSelect} disabled={isConverting} />

                    {isConverting && (
                        <output
                            data-testid="loading-indicator"
                            className="mt-6 flex flex-col items-center gap-3 py-8"
                        >
                            <div className="animate-spin w-8 h-8 border-4 border-red-700 border-t-transparent rounded-full" />
                            <p className="text-gray-500 text-sm">Converting...</p>
                        </output>
                    )}

                    {error && (
                        <div
                            role="alert"
                            className="mt-4 flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
                        >
                            <span aria-hidden>⚠</span>
                            <span>{error}</span>
                        </div>
                    )}

                    {outputFile && !error && (
                        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                            <p className="font-semibold text-gray-800">{outputFile.filename}</p>
                            <p className="text-sm text-gray-500 mt-1">Format: {outputFile.format}</p>
                            <p className="text-sm text-gray-500" data-testid="file-size">
                                Size: {Math.round(outputFile.size / 1024)} KB
                            </p>
                            <button
                                data-testid="download-btn"
                                onClick={() => {
                                    const dummyData = new Uint8Array(outputFile.size);
                                    const blob = new Blob([dummyData], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement("a");
                                    a.href = url;
                                    a.download = outputFile.filename;
                                    document.body.appendChild(a);
                                    a.click();
                                    a.remove();
                                    URL.revokeObjectURL(url);
                                }}
                                disabled={!outputFile}
                                className="mt-4 bg-red-700 text-white font-bold px-6 py-2 rounded-xl hover:bg-red-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Download
                            </button>
                        </div>
                    )}
                </div>
            </main>
        </div>
    )
}