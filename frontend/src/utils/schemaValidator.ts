export type JsonObject = Record<string, unknown>;
export type JsonArray = unknown[];
export type JsonValue = JsonObject | JsonArray;
export function isJsonObjectOrArray(value: unknown): value is JsonValue {
    return typeof value === "object" && value !== null;
}
