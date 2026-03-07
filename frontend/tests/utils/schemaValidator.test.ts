import { describe, expect, it } from "vitest";
import { isJsonObjectOrArray } from "@/utils/schemaValidator";

describe("isJsonObjectOrArray", () => {

    it("returns true for a plain object", () => {
        expect(isJsonObjectOrArray({ a: 1 })).toBe(true);
    });

    it("returns true for an empty object", () => {
        expect(isJsonObjectOrArray({})).toBe(true);
    });

    it("returns true for an array with items", () => {
        expect(isJsonObjectOrArray([1, 2, 3])).toBe(true);
    });

    it("returns true for an empty array", () => {
        expect(isJsonObjectOrArray([])).toBe(true);
    });

    it("returns true for a nested object", () => {
        expect(isJsonObjectOrArray({ rows: [{ id: 1 }] })).toBe(true);
    });

    it("returns false for a string", () => {
        expect(isJsonObjectOrArray("hello")).toBe(false);
    });

    it("returns false for a number", () => {
        expect(isJsonObjectOrArray(42)).toBe(false);
    });

    it("returns false for a boolean", () => {
        expect(isJsonObjectOrArray(true)).toBe(false);
    });

    it("returns false for null", () => {
        expect(isJsonObjectOrArray(null)).toBe(false);
    });

    it("returns false for undefined", () => {
        expect(isJsonObjectOrArray(undefined)).toBe(false);
    });

    it("returns false for a Date instance", () => {
        expect(isJsonObjectOrArray(new Date())).toBe(false);
    });

    it("returns false for a Map instance", () => {
        expect(isJsonObjectOrArray(new Map())).toBe(false);
    });
});
