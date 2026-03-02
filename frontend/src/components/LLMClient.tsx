"use client";

import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { atomDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { generateJson } from "@/services/llm";
import type { LLMResponse } from "@/services/llm";

function SkeletonLoader() {
    return (
        <div className="animate-pulse space-y-3 pt-2">
            <div className="h-4 w-full rounded bg-gray-600" />
            <div className="h-4 w-5/6 rounded bg-gray-600" />
            <div className="h-4 w-4/6 rounded bg-gray-600" />
            <div className="h-4 w-3/6 rounded bg-gray-600" />
        </div>
    );
}

function Alert({ message }: { message: string }) {
    return (
        <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700"
        >
            <span className="mt-0.5 shrink-0 text-red-500">⚠</span>
            <span>{message}</span>
        </div>
    );
}

export default function LLMClient() {
    const [input, setInput] = useState<string>("");
    const [result, setResult] = useState<LLMResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(false);

    async function handleSubmit() {
        setError(null);
        setResult(null);

        if (!input.trim()) {
            setError("Input tidak boleh kosong");
            return;
        }

        let parsedInput: Record<string, unknown>;
        try {
            parsedInput = JSON.parse(input);
        } catch {
            setError("Input harus berupa JSON yang valid");
            return;
        }

        setLoading(true);
        try {
            const response = await generateJson(parsedInput);
            setResult(response);
        } catch (err: unknown) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Terjadi kesalahan tidak diketahui"
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen bg-gray-950 px-4 py-8 lg:px-8">
            <div className="mx-auto max-w-5xl">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight text-white">
                        LLM JSON Generator
                    </h1>
                    <p className="mt-1 text-sm text-gray-400">
                        Masukkan JSON, klik Generate, dan dapatkan output terstruktur dari LLM.
                    </p>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

                    <div className="flex flex-col rounded-2xl bg-gray-800/60 p-5 shadow-xl ring-1 ring-white/5">
                        <label
                            htmlFor="llm-input"
                            className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400"
                        >
                            Input JSON
                        </label>
                        <textarea
                            id="llm-input"
                            aria-label="input"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={'{\n  "key": "value"\n}'}
                            rows={12}
                            spellCheck={false}
                            className="flex-1 resize-none rounded-xl bg-gray-900 p-4 font-mono text-sm leading-relaxed text-gray-100 outline-none placeholder:text-gray-600 focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                            onClick={handleSubmit}
                            disabled={loading}
                            className="mt-4 w-full rounded-xl bg-blue-600 py-2.5 text-sm font-semibold text-white shadow-md transition-all duration-150 hover:bg-blue-500 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {loading ? "Generating…" : "Generate"}
                        </button>
                    </div>

                    <div className="flex flex-col rounded-2xl bg-gray-800/60 p-5 shadow-xl ring-1 ring-white/5">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
                            Output
                        </p>

                        {loading && <SkeletonLoader />}
                        {!loading && error && <Alert message={error} />}
                        {!loading && result && (
                            <SyntaxHighlighter
                                language="json"
                                style={atomDark}
                                customStyle={{
                                    borderRadius: "0.75rem",
                                    margin: 0,
                                    fontSize: "0.8125rem",
                                    lineHeight: "1.6",
                                    flex: 1,
                                }}
                                wrapLongLines
                            >
                                {JSON.stringify(result.output_json, null, 2)}
                            </SyntaxHighlighter>
                        )}

                        {!loading && !error && !result && (
                            <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-gray-700 py-16 text-sm text-gray-600">
                                Hasil akan tampil di sini
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
