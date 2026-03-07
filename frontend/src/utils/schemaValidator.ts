export type JsonObject = Record<string, unknown>;
export type JsonArray = unknown[];
export type JsonValue = JsonObject | JsonArray;
export function isJsonObjectOrArray(value: unknown): value is JsonValue {
    if (typeof value !== "object" || value === null) {
        return false;
    }
    return Array.isArray(value) || Object.getPrototypeOf(value) === Object.prototype;
}
