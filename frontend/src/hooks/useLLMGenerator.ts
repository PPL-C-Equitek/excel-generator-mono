"use client";

import { useRef, useState } from "react";
import { isJsonObjectOrArray } from "@/utils/schemaValidator";
import type { JsonValue } from "@/utils/schemaValidator";
import type { LLMResponse } from "@/services/llm";
import type { ILLMService } from "@/lib/ILLMService";

export interface UseLLMGeneratorReturn {
    input: string;
    setInput: (value: string) => void;
    result: LLMResponse | null;
    error: string | null;
    loading: boolean;
    handleSubmit: () => Promise<void>;
}

export function useLLMGenerator(service: ILLMService): UseLLMGeneratorReturn {
    const [input, setInput] = useState<string>("");
    const [result, setResult] = useState<LLMResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const requestIdRef = useRef<number>(0);

    async function handleSubmit(): Promise<void> {
        setError(null);
        setResult(null);

        if (!input.trim()) {
            setError("Input tidak boleh kosong");
            return;
        }

        let parsedInput: JsonValue;
        try {
            const raw: unknown = JSON.parse(input);
            if (!isJsonObjectOrArray(raw)) {
                setError("Input harus berupa JSON object atau array");
                return;
            }
            parsedInput = raw;
        } catch {
            setError("Input harus berupa JSON yang valid");
            return;
        }
        requestIdRef.current += 1;
        const currentRequestId = requestIdRef.current;

        setLoading(true);
        try {
            const response = await service.generate(parsedInput);
            if (currentRequestId !== requestIdRef.current) return;
            setResult(response);
        } catch (err: unknown) {
            if (currentRequestId !== requestIdRef.current) return;
            setError(
                err instanceof Error
                    ? err.message
                    : "Terjadi kesalahan tidak diketahui"
            );
        } finally {
            if (currentRequestId === requestIdRef.current) {
                setLoading(false);
            }
        }
    }

    return { input, setInput, result, error, loading, handleSubmit };
}
