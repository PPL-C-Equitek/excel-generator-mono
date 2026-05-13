import type { JsonValue } from "@/utils/schemaValidator";
import type { ExcelExportResponse, LLMResponse } from "@/services/llm";

export interface ILLMService {
    generate: (
        inputJson: JsonValue,
        customSchemaId?: string | null,
        signal?: AbortSignal,
        context?: {
            sessionId?: string | null;
            chatId?: string | null;
        }
    ) => Promise<LLMResponse>;
    exportToCsv?: (
        outputJson: JsonValue,
        signal?: AbortSignal
    ) => Promise<{ file_id: string }>;
    downloadCsvFile?: (fileId: string, filename?: string) => Promise<void>;
    exportToExcel?: (
        outputJson: JsonValue,
        signal?: AbortSignal
    ) => Promise<ExcelExportResponse>;
    downloadExcelFile?: (fileId: string, filename?: string) => Promise<void>;
    downloadSessionOutputCsvFile?: (
        sessionId: string,
        outputId: string,
        filename?: string
    ) => Promise<void>;
    downloadSessionOutputExcelFile?: (
        sessionId: string,
        outputId: string,
        filename?: string
    ) => Promise<void>;
    getDownloadUrl?: (fileId: string, filename?: string) => string;
}
