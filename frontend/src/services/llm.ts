import { fetchAPI } from "@/lib/api";
import { ERROR_MESSAGES } from "@/constants/errorMessages";
import { isJsonObject } from "@/utils/schemaValidator";
import type { JsonValue } from "@/utils/schemaValidator";
export { ERROR_MESSAGES } from "@/constants/errorMessages";
export type { JsonValue } from "@/utils/schemaValidator";



export interface LLMRequest {
    input_json: JsonValue;
}

export interface LLMResponse {
    output_json: JsonValue;
}

export interface ExcelExportResponse {
    file_id: string;
    file_name: string;
    artifact_type: "xlsx";
}

const EXCEL_EXPORT_ERROR_MESSAGE = "The Excel export response is invalid.";
const EXCEL_DOWNLOAD_ERROR_MESSAGE = "Failed to export";

function getErrorStatus(err: Error): number | null {
    const errorWithStatus = err as Error & { status?: number };
    if (typeof errorWithStatus.status === "number") {
        return errorWithStatus.status;
    }

    const statusMatch = /API error: (\d+)/.exec(err.message);
    if (statusMatch) {
        return Number.parseInt(statusMatch[1], 10);
    }

    return null;
}

function rethrowMappedApiError(err: unknown): never {
    if (err instanceof Error) {
        const status = getErrorStatus(err);
        if (status !== null) {
            const userMessage = ERROR_MESSAGES[status];
            if (userMessage) {
                throw new Error(userMessage);
            }
        }
    }

    throw err;
}

export async function generateJson(
    inputJson: JsonValue
): Promise<LLMResponse> {
    const isEmpty = Array.isArray(inputJson)
        ? inputJson.length === 0
        : Object.keys(inputJson).length === 0;

    if (isEmpty) {
        throw new Error("Input cannot be empty.");
    }

    let data: unknown;

    try {
        data = await fetchAPI("llm/generate/", {
            method: "POST",
            body: JSON.stringify({ input_json: inputJson }),
        });
    } catch (err: unknown) {
        rethrowMappedApiError(err);
    }

    if (
        typeof data !== "object" ||
        data === null ||
        !("output_json" in data) ||
        !isJsonObject((data as Record<string, unknown>)["output_json"])
    ) {
        throw new Error("The server returned an invalid response.");
    }

    return data as LLMResponse;
}

function getApiBaseOrigin(): string {
    try {
        return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").origin;
    } catch {
        return "http://localhost:8000";
    }
}

function isValidExcelExportResponse(data: unknown): data is ExcelExportResponse {
    if (typeof data !== "object" || data === null) {
        return false;
    }

    const response = data as Record<string, unknown>;
    return (
        typeof response.file_id === "string" &&
        response.file_id.startsWith("xlsx_") &&
        typeof response.file_name === "string" &&
        response.file_name.endsWith(".xlsx") &&
        response.artifact_type === "xlsx"
    );
}

function assertValidExcelDownloadFileId(fileId: string): void {
    if (typeof fileId !== "string" || !fileId.startsWith("xlsx_")) {
        throw new Error("The Excel download request is invalid.");
    }
}

function cleanupExcelDownloadResources(
    downloadAnchor: HTMLAnchorElement | null,
    objectUrl: string | null,
    appendedToBody: boolean
): void {
    if (downloadAnchor && appendedToBody) {
        document.body.removeChild(downloadAnchor);
    }

    if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
    }
}

/**
 * Mengekspor hasil generasi JSON ke format CSV.
 * Berkomunikasi dengan endpoint REST (POST /export/csv)
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
        data = await fetchAPI("export/csv", {
            method: "POST",
            body: JSON.stringify({ output_json: outputJson }),
        });
    } catch (err: unknown) {
        rethrowMappedApiError(err);
    }

    if (
        typeof data !== "object" ||
        data === null ||
        !("file_id" in data) ||
        typeof (data as Record<string, unknown>).file_id !== "string" ||
        !(data as Record<string, string>).file_id.startsWith("csv_")
    ) {
        throw new Error("The CSV export response is invalid.");
    }

    return { file_id: (data as Record<string, string>).file_id };
}

export async function exportToExcel(
    outputJson: JsonValue
): Promise<ExcelExportResponse> {
    let data: unknown;

    try {
        data = await fetchAPI("export/excel", {
            method: "POST",
            body: JSON.stringify({ output_json: outputJson }),
        });
    } catch (err: unknown) {
        rethrowMappedApiError(err);
    }

    if (!isValidExcelExportResponse(data)) {
        throw new Error(EXCEL_EXPORT_ERROR_MESSAGE);
    }

    return {
        file_id: data.file_id,
        file_name: data.file_name,
        artifact_type: data.artifact_type,
    };
}

export async function downloadExcelFile(
    fileId: string,
    filename = "export.xlsx"
): Promise<void> {
    assertValidExcelDownloadFileId(fileId);

    let objectUrl: string | null = null;
    let downloadAnchor: HTMLAnchorElement | null = null;
    let appendedToBody = false;

    try {
        const response = await fetch(
            `${getApiBaseOrigin()}/export/excel/${fileId}/download`,
            { method: "GET" }
        );

        if (!response.ok) {
            throw new Error(EXCEL_DOWNLOAD_ERROR_MESSAGE);
        }

        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);

        downloadAnchor = document.createElement("a");
        downloadAnchor.href = objectUrl;
        downloadAnchor.download = filename;
        document.body.appendChild(downloadAnchor);
        appendedToBody = true;
        downloadAnchor.click();
    } catch (err: unknown) {
        if (
            err instanceof Error &&
            err.message === "The Excel download request is invalid."
        ) {
            throw err;
        }
        throw new Error(EXCEL_DOWNLOAD_ERROR_MESSAGE);
    } finally {
        cleanupExcelDownloadResources(downloadAnchor, objectUrl, appendedToBody);
    }
}

/**
 * Menghasilkan URL lengkap untuk mengunduh hasil konversi CSV.
 * Pemanggilan URL ini akan menuju ke GET /export/csv/{fileId}/download
 * bersama param filename opsional.
 *
 * @param fileId string ID dengan prefix 'csv_'.
 * @param filename Opsional, nama file target untuk download.
 * @returns URL valid untuk pengunduhan file dari API backend.
 */
export function getDownloadUrl(fileId: string, filename?: string): string {
    const base = getApiBaseOrigin();
    let url = `${base}/export/csv/${fileId}/download`;
    if (filename) {
        url += `?filename=${encodeURIComponent(filename)}`;
    }
    return url;
}
