import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import { generateJson, exportToCsv, getDownloadUrl } from "@/services/llm";
import { server } from "../mocks/server";
import {
  handler401,
  handler429,
  handler504,
  handlerArrayOutput,
  handlerInvalidSchema,
  handlerPrimitiveOutput,
  successHandler,
  exportCsvSuccessHandler,
  exportCsvInvalidPrefixHandler,
  exportCsvInvalidSchemaHandler,
} from "../mocks/handlers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

describe("generateJson positive", () => {
  beforeEach(() => {
    server.use(successHandler);
  });

  it("returns output_json for valid payload", async () => {
    const result = await generateJson({ key: "value" });

    expect(result).toHaveProperty("output_json");
    expect(result.output_json).toMatchObject({
      summary: "Data extracted successfully",
      rows: [{ id: 1, value: "test" }],
    });
  });
});

describe("generateJson negative (HTTP errors)", () => {
  it("maps 401 to user-friendly message", async () => {
    server.use(handler401);
    await expect(generateJson({ key: "value" })).rejects.toThrow("API Key tidak valid");
  });

  it("maps 429 to user-friendly message", async () => {
    server.use(handler429);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Quota LLM habis, coba lagi nanti");
  });

  it("maps 504 to user-friendly message", async () => {
    server.use(handler504);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Request timeout, coba lagi");
  });

  it("maps 503 to user-friendly message", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ detail: "Service Unavailable" }, { status: 503 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow(
      "Server sedang tidak tersedia, coba lagi nanti"
    );
  });

  it("keeps original API error when status is not mapped", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ detail: "Teapot" }, { status: 418 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow("API error: 418");
  });
});

describe("generateJson edge cases", () => {
  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  it("throws validation error for empty input", async () => {
    await expect(generateJson({})).rejects.toThrow("Input tidak boleh kosong");
  });

  it("throws validation error for empty array input", async () => {
    await expect(generateJson([])).rejects.toThrow("Input tidak boleh kosong");
  });

  it("throws schema error when output_json is missing", async () => {
    server.use(handlerInvalidSchema);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Respons tidak sesuai skema");
  });

  it("rethrows non-API Error as-is", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("Network down"));
    await expect(generateJson({ key: "value" })).rejects.toThrow("Network down");
  });

  it("rethrows non-Error rejection as-is", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue("fatal");
    await expect(generateJson({ key: "value" })).rejects.toBe("fatal");
  });
});

describe("generateJson array input & schema type validation", () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it("throws schema error when output_json is an array", async () => {
    server.use(handlerArrayOutput);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Respons tidak sesuai skema");
  });

  it("throws schema error when output_json is a primitive string", async () => {
    server.use(handlerPrimitiveOutput);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Respons tidak sesuai skema");
  });

  it("throws schema error when output_json is a primitive number", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ output_json: 42 }, { status: 200 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow("Respons tidak sesuai skema");
  });
});

describe("exportToCsv", () => {
  const mockJson = { status: "ok" };

  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  it("returns file_id on successful export", async () => {
    server.use(exportCsvSuccessHandler);
    const result = await exportToCsv(mockJson);
    expect(result).toEqual({ file_id: "csv_12345" });
  });

  it("throws error if response does not contain file_id", async () => {
    server.use(exportCsvInvalidSchemaHandler);
    await expect(exportToCsv(mockJson)).rejects.toThrow("Respons ekspor CSV tidak valid");
  });

  it("throws error if file_id does not have 'csv_' prefix", async () => {
    server.use(exportCsvInvalidPrefixHandler);
    await expect(exportToCsv(mockJson)).rejects.toThrow("Respons ekspor CSV tidak valid");
  });

  it("maps HTTP errors properly using existing ERROR_MESSAGES", async () => {
    server.use(
      http.post(`${API_BASE}/api/export/csv`, () =>
        HttpResponse.json({ detail: "Gateway Timeout" }, { status: 504 })
      )
    );
    await expect(exportToCsv(mockJson)).rejects.toThrow("Request timeout, coba lagi");
  });

  it("passes through unmapped HTTP errors", async () => {
    server.use(
      http.post(`${API_BASE}/api/export/csv`, () =>
        HttpResponse.json({ detail: "Teapot" }, { status: 418 })
      )
    );
    await expect(exportToCsv(mockJson)).rejects.toThrow("API error: 418");
  });

  it("passes through unknown errors from fetchAPI", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("Unknown Failure"));
    await expect(exportToCsv(mockJson)).rejects.toThrow("Unknown Failure");
  });

  it("passes through non-Error rejections", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue("String Failure");
    await expect(exportToCsv(mockJson)).rejects.toBe("String Failure");
  });
});

describe("getDownloadUrl", () => {
  it("returns a valid download URL without filename", () => {
    const url = getDownloadUrl("csv_abc");
    expect(url).toBe(`${API_BASE}/api/export/csv/csv_abc/download`);
  });

  it("appends and URI-encodes the filename parameter", () => {
    const url = getDownloadUrl("csv_abc", "laporan keuangan 2024.csv");
    expect(url).toBe(`${API_BASE}/api/export/csv/csv_abc/download?filename=laporan%20keuangan%202024.csv`);
  });

  it("falls back to localhost:8000 if URL parsing fails", () => {
    // This requires manipulating process.env or mocking URL for the try-catch block inside getDownloadUrl
    // We can simulate it by setting a malformed NEXT_PUBLIC_API_URL temporarily if doing so is simple:
    const original = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "htt   p://in^valid\nurl"; // triggers URL constructor error
    
    // Note: getDownloadUrl initializes NEXT_PUBLIC_API_URL locally in its body each call
    const url = getDownloadUrl("csv_abc");
    expect(url).toBe("http://localhost:8000/api/export/csv/csv_abc/download");
    
    process.env.NEXT_PUBLIC_API_URL = original;
  });
});
