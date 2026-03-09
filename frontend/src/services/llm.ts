import { fetchAPI } from "@/lib/api";
import { ERROR_MESSAGES } from "@/constants/errorMessages";
import { isJsonObject } from "@/utils/schemaValidator";
import type { JsonValue } from "@/utils/schemaValidator";
export { ERROR_MESSAGES };
export type { JsonValue } from "@/utils/schemaValidator";



export interface LLMRequest {
    input_json: JsonValue;
}

export interface LLMResponse {
    output_json: JsonValue;
}

export async function generateJson(
    inputJson: JsonValue
): Promise<LLMResponse> {
    const isEmpty = Array.isArray(inputJson)
        ? inputJson.length === 0
        : Object.keys(inputJson).length === 0;

    if (isEmpty) {
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
        !("output_json" in data) ||
        !isJsonObject((data as Record<string, unknown>)["output_json"])
    ) {
        throw new Error("Respons tidak sesuai skema");
    }

    return data as LLMResponse;
}