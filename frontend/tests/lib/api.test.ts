import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAPI, uploadFile } from "@/lib/api";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe("fetchAPI", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        vi.unstubAllEnvs();
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

    it("strips trailing slash from NEXT_PUBLIC_API_URL before building request URL", async () => {
        vi.resetModules();
        vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:9999/");

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ status: "trimmed" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const { fetchAPI: freshFetchAPI } = await import("@/lib/api");
        const result = await freshFetchAPI("health/");

        const calledUrl = mockedFetch.mock.calls[0][0] as string;
        expect(calledUrl).toBe("http://localhost:9999/health/");
        expect(result).toEqual({ status: "trimmed" });
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
        vi.unstubAllEnvs();
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
            "http://localhost:8000/upload/",
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

    it("maps max file size upload error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "File too large. Maximum allowed size is 10MB." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "big.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("File size too big.");
    });

    it("maps max PDF page count error to user-friendly FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message: "PDF exceeds the maximum allowed page count of 100.",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "long.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("PDF has too many pages (maximum 100).");
    });

    it("maps password-protected PDF error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "The PDF file is password-protected." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "protected.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow(
            "PDF is password-protected. Please remove the password and try again."
        );
    });

    it("maps password-protected Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                message:
                    "The Excel file is password-protected. Please remove the password and try again.",
            }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "protected.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        await expect(uploadFile(file)).rejects.toThrow(
            "Excel is password-protected. Please remove the password and try again."
        );
    });

    it("maps corrupted PDF error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "The PDF file is corrupt or has an invalid structure." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.pdf", { type: "application/pdf" });

        await expect(uploadFile(file)).rejects.toThrow("PDF file is corrupted or invalid.");
    });

    it("maps generic corrupted Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "Invalid or corrupted Excel file." }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel file is corrupted or invalid.");
    });

    it("maps parser-level corrupted Excel error to dedicated FE message", async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: "File Excel corrupted atau cannot read: broken stream" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const file = new File(["file-content"], "corrupt.xls", {
            type: "application/vnd.ms-excel",
        });

        await expect(uploadFile(file)).rejects.toThrow("Excel file is corrupted or invalid.");
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

    it("falls back to localhost:8000 when NEXT_PUBLIC_API_URL is not a valid URL", async () => {
        vi.resetModules();
        vi.stubEnv("NEXT_PUBLIC_API_URL", "not-a-valid-url");

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ message: "ok" }),
        });
        vi.stubGlobal("fetch", mockedFetch);

        const { uploadFile: freshUploadFile } = await import("@/lib/api");
        const file = new File(["content"], "test.pdf", { type: "application/pdf" });
        await freshUploadFile(file);

        const calledUrl = mockedFetch.mock.calls[0][0] as string;
        expect(calledUrl).toBe("http://localhost:8000/upload/");
    });
});
