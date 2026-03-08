import { describe, expect, it } from "vitest";
import { isJsonObject } from "@/utils/schemaValidator";

describe("isJsonObject", () => {

    it("returns true for a plain object", () => {
        expect(isJsonObject({ a: 1 })).toBe(true);
    });

    it("returns true for an empty object", () => {
        expect(isJsonObject({})).toBe(true);
    });

    it("returns false for an array with items", () => {
        expect(isJsonObject([1, 2, 3])).toBe(false);
    });

    it("returns false for an empty array", () => {
        expect(isJsonObject([])).toBe(false);
    });

    it("returns true for a nested object", () => {
        expect(isJsonObject({ rows: [{ id: 1 }] })).toBe(true);
    });

    it("returns false for a string", () => {
        expect(isJsonObject("hello")).toBe(false);
    });

    it("returns false for a number", () => {
        expect(isJsonObject(42)).toBe(false);
    });

    it("returns false for a boolean", () => {
        expect(isJsonObject(true)).toBe(false);
    });

    it("returns false for null", () => {
        expect(isJsonObject(null)).toBe(false);
    });

    it("returns false for undefined", () => {
        expect(isJsonObject(undefined)).toBe(false);
    });

    it("returns false for a Date instance", () => {
        expect(isJsonObject(new Date())).toBe(false);
    });

    it("returns false for a Map instance", () => {
        expect(isJsonObject(new Map())).toBe(false);
    });
});
