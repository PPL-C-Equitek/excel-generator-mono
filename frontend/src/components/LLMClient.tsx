"use client";

import { useState } from "react";
import { generateJson, LLMResponse } from "@/services/llm";

export default function LLMClient() {
    const [input, setInput] = useState("");
    const [result, setResult] = useState<LLMResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

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
            if (err instanceof Error) {
                setError(err.message);
            } else {
                setError("Terjadi kesalahan tidak diketahui");
            }
        } finally {
            setLoading(false);
        }
    }

    return (
        <div>
            <textarea
                aria-label="input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder='Masukkan JSON, contoh: {"key": "value"}'
                rows={6}
                style={{ width: "100%", fontFamily: "monospace" }}
            />

            <button onClick={handleSubmit} disabled={loading}>
                Generate
            </button>

            {loading && <p>Loading...</p>}

            {error && (
                <p role="alert" style={{ color: "red" }}>
                    {error}
                </p>
            )}

            {result && (
                <pre data-testid="llm-result">
                    {JSON.stringify(result.output_json, null, 2)}
                </pre>
            )}
        </div>
    );
}
