import type { JsonValue } from "@/utils/schemaValidator";
import type { ExcelExportResponse, LLMResponse } from "@/services/llm";

export interface ILLMService {
    generate: (inputJson: JsonValue, customSchemaId?: string | null) => Promise<LLMResponse>;
    exportToCsv?: (outputJson: JsonValue) => Promise<{ file_id: string }>;
    downloadCsvFile?: (fileId: string, filename?: string) => Promise<void>;
    exportToExcel?: (outputJson: JsonValue) => Promise<ExcelExportResponse>;
    downloadExcelFile?: (fileId: string, filename?: string) => Promise<void>;
    getDownloadUrl?: (fileId: string, filename?: string) => string;
}
