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

/**
 * Mengekspor hasil generasi JSON ke format CSV.
 * Berkomunikasi dengan endpoint REST (POST /api/export/csv)
 * dan mengembalikan file_id dengan prefix keamanan 'csv_'.
 *
 * @param outputJson JSON hasil LLM yang valid.
 * @returns Promise berisi file_id yang digenerate oleh backend.
 */
export async function exportToCsv(
    outputJson: JsonValue
): Promise<{ file_id: string }> {
    let data: unknown;

    try {
        data = await fetchAPI("api/export/csv", {
            method: "POST",
            body: JSON.stringify({ output_json: outputJson }),
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
        !("file_id" in data) ||
        typeof (data as Record<string, unknown>).file_id !== "string" ||
        !(data as Record<string, string>).file_id.startsWith("csv_")
    ) {
        throw new Error("Respons ekspor CSV tidak valid");
    }

    return { file_id: (data as Record<string, string>).file_id };
}

/**
 * Menghasilkan URL lengkap untuk mengunduh hasil konversi CSV.
 * Pemanggilan URL ini akan menuju ke GET /api/export/csv/{fileId}/download
 * bersama param filename opsional.
 *
 * @param fileId string ID dengan prefix 'csv_'.
 * @param filename Opsional, nama file target untuk download.
 * @returns URL valid untuk pengunduhan file dari API backend.
 */
export function getDownloadUrl(fileId: string, filename?: string): string {
    const base = (() => {
        try {
            return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").origin;
        } catch {
            return "http://localhost:8000";
        }
    })();
    let url = `${base}/api/export/csv/${fileId}/download`;
    if (filename) {
        url += `?filename=${encodeURIComponent(filename)}`;
    }
    return url;
}
