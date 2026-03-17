"use client";

import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { isJsonObject } from "@/utils/schemaValidator";
import type { JsonValue } from "@/utils/schemaValidator";
import type { LLMResponse } from "@/services/llm";
import type { ILLMService } from "@/lib/ILLMService";

export interface UseLLMGeneratorReturn {
    input: string;
    setInput: Dispatch<SetStateAction<string>>;
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
            setError("Input cannot be empty.");
            return;
        }

        let parsedInput: JsonValue;
        try {
            const raw: unknown = JSON.parse(input);
            if (!isJsonObject(raw)) {
                setError("Input must be a JSON object.");
                return;
            }
            parsedInput = raw;
        } catch {
            setError("Input must be valid JSON.");
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
                    : "An unknown error occurred."
            );
        } finally {
            if (currentRequestId === requestIdRef.current) {
                setLoading(false);
            }
        }
    }

    return { input, setInput, result, error, loading, handleSubmit };
}
