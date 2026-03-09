import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import { generateJson } from "@/services/llm";
import { server } from "../mocks/server";
import {
  handler401,
  handler429,
  handler504,
  handlerArrayOutput,
  handlerInvalidSchema,
  handlerPrimitiveOutput,
  successHandler,
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
