import type { JsonValue } from "@/utils/schemaValidator";
import type { LLMResponse } from "@/services/llm";

export interface ILLMService {
    generate: (inputJson: JsonValue) => Promise<LLMResponse>;
}
