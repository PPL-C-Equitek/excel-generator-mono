import { fetchAPI } from "@/lib/api";

export interface LLMRequest {
    input_json: Record<string, unknown>;
    model?: string;
}

export interface LLMResponse {
    output_json: Record<string, unknown>;
}

const ERROR_MESSAGES: Record<number, string> = {
    401: "API Key tidak valid",
    429: "Quota LLM habis, coba lagi nanti",
    504: "Request timeout, coba lagi",
};

export async function generateJson(
    inputJson: Record<string, unknown>
): Promise<LLMResponse> {
    if (Object.keys(inputJson).length === 0) {
        throw new Error("Input tidak boleh kosong");
    }

    let data: unknown;

    try {
        data = await fetchAPI("llm/generate/", {
            method: "POST",
            body: JSON.stringify({ input_json: inputJson }),
        });
    } catch (err: unknown) {
        if (err instanceof Error) {
            const statusMatch = err.message.match(/API error: (\d+)/);
            if (statusMatch) {
                const status = parseInt(statusMatch[1], 10);
                const userMessage = ERROR_MESSAGES[status];
                if (userMessage) {
                    throw new Error(userMessage);
                }
            }
        }
        throw err;
    }

    if (
        typeof data !== "object" ||
        data === null ||
        !("output_json" in data)
    ) {
        throw new Error("Respons tidak sesuai skema");
    }

    return data as LLMResponse;
}
