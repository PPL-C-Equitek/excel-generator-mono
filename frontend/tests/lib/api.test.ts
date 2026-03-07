import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAPI, uploadFile } from "@/lib/api";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe("fetchAPI", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("calls API endpoint and returns parsed JSON", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: "ok" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const result = await fetchAPI("health/");

        expect(mockedFetch).toHaveBeenCalledWith("http://localhost:8000/health/", {
            headers: {
                "Content-Type": "application/json",
            },
        });
        expect(result).toEqual({ status: "ok" });
    });

    it("throws error when response is not OK", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({}),
        });
        vi.stubGlobal("fetch", mockedFetch);

        await expect(fetchAPI("health/")).rejects.toThrow("API error: 500");
    });
});

describe("uploadFile", () => {
    beforeEach(() => {
        delete process.env.NEXT_PUBLIC_API_URL;
    });

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("uploads file as FormData and returns parsed response", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 201,
            json: async () => ({ message: "uploaded" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "report.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        const result = await uploadFile(file);

        expect(mockedFetch).toHaveBeenCalledWith(
            "http://localhost:8000/api/upload/",
            expect.objectContaining({
                method: "POST",
                body: expect.any(FormData),
            })
        );
        expect(result).toEqual({ message: "uploaded" });
    });

    it("throws API error message when upload fails with message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Invalid file" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "bad.txt", { type: "text/plain" });

        await expect(uploadFile(file)).rejects.toThrow("Invalid file");
    });

    it("throws default error when upload fails without message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({}),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "bad.txt", { type: "text/plain" });

        await expect(uploadFile(file)).rejects.toThrow("Upload failed");
    });
});
