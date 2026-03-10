export type JsonObject = Record<string, unknown>;
export type JsonArray = unknown[];
export type JsonValue = JsonObject | JsonArray;
export function isJsonObject(value: unknown): value is JsonObject {
    if (typeof value !== "object" || value === null) {
        return false;
    }
    return Object.getPrototypeOf(value) === Object.prototype;
}