/**
 * [RED] — Tests for generateJson() service
 *
 * These tests use MSW to intercept HTTP at the network layer.
 * All tests will FAIL until src/services/llm.ts is implemented.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { server } from "@/__mocks__/server";
import {
    handler401,
    handler429,
    handler504,
    handlerInvalidSchema,
    successHandler,
} from "@/__mocks__/handlers";
import { generateJson } from "@/services/llm";

describe("generateJson — Positive", () => {
    beforeEach(() => {
        server.use(successHandler);
    });

    it("mengirim input_json dan mengembalikan output_json yang valid", async () => {
        const result = await generateJson({ key: "value" });

        expect(result).toHaveProperty("output_json");
        expect(result.output_json).toMatchObject({
            summary: "Data extracted successfully",
            rows: [{ id: 1, value: "test" }],
        });
    });
});

describe("generateJson — Negative (HTTP Errors)", () => {
    it("melempar error dengan pesan jelas saat API Key invalid (401)", async () => {
        server.use(handler401);

        await expect(generateJson({ key: "value" })).rejects.toThrow(
            "API Key tidak valid"
        );
    });

    it("melempar error dengan pesan jelas saat quota habis (429)", async () => {
        server.use(handler429);

        await expect(generateJson({ key: "value" })).rejects.toThrow(
            "Quota LLM habis, coba lagi nanti"
        );
    });

    it("melempar error dengan pesan jelas saat timeout (504)", async () => {
        server.use(handler504);

        await expect(generateJson({ key: "value" })).rejects.toThrow(
            "Request timeout, coba lagi"
        );
    });
});

describe("generateJson — Edge Cases", () => {
    afterEach(() => {
        server.resetHandlers();
    });

    it("melempar error validasi saat input kosong (object kosong)", async () => {
        await expect(generateJson({})).rejects.toThrow("Input tidak boleh kosong");
    });

    it("melempar error schema saat respons tidak memiliki field output_json", async () => {
        server.use(handlerInvalidSchema);

        await expect(generateJson({ key: "value" })).rejects.toThrow(
            "Respons tidak sesuai skema"
        );
    });
});
