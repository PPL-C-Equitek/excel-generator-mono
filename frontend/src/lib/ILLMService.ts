import type { JsonValue } from "@/utils/schemaValidator";
import type { LLMResponse } from "@/services/llm";

export interface ILLMService {
    generate: (inputJson: JsonValue) => Promise<LLMResponse>;
    exportToCsv?: (outputJson: JsonValue) => Promise<{ file_id: string }>;
    getDownloadUrl?: (fileId: string, filename?: string) => string;
}
