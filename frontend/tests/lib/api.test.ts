import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAPI } from "@/lib/api";

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
