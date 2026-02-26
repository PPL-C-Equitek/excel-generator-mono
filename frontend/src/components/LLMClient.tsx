"use client";

import { useState } from "react";
import { generateJson } from "@/services/llm";

export default function LLMClient() {
    const [input, setInput] = useState("");
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleGenerate = async () => {
        setError(null);
        
        if (!input) {
            setError("Input tidak boleh kosong");
            return;
        }

        setLoading(true);
        try {
            const body = JSON.parse(input);
            const res = await generateJson(body);
            setResult(res);
        } catch (e: any) {
            setError(e.message || "Error");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <textarea 
                aria-label="input"
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
            />
            <button onClick={handleGenerate} disabled={loading}>
                {loading ? "Loading..." : "Generate"}
            </button>
            
            {error && <p role="alert">{error}</p>}
            
            {result && (
                <pre data-testid="llm-result">
                    {JSON.stringify(result.output_json)}
                </pre>
            )}
        </div>
    );
}