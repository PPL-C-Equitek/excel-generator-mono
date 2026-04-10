import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import * as auth from "@/lib/auth";
import * as llmService from "@/services/llm";
import { downloadCsvFile, generateJson, exportToCsv, getDownloadUrl } from "@/services/llm";
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
  exportExcelSuccessHandler,
  exportExcelInvalidSchemaHandler,
  exportExcelInvalidPrefixHandler,
  exportExcelInvalidArtifactTypeHandler,
  exportExcelInvalidFileNameHandler,
} from "../mocks/handlers";

vi.mock("@/lib/auth", () => ({
  getStoredAccessToken: vi.fn(),
  getValidAccessToken: vi.fn(),
}));

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ExcelServiceModule = typeof llmService & {
  exportToExcel: (outputJson: unknown) => Promise<{
    file_id: string;
    file_name: string;
    artifact_type: string;
  }>;
  downloadExcelFile: (fileId: string, filename?: string) => Promise<void>;
};

const excelService = llmService as ExcelServiceModule;
const mockGetStoredAccessToken = vi.mocked(auth.getStoredAccessToken);
const mockGetValidAccessToken = vi.mocked(auth.getValidAccessToken);

describe("generateJson positive", () => {
  beforeEach(() => {
    server.use(successHandler);
    mockGetStoredAccessToken.mockReturnValue(null);
  });

  it("returns output_json for valid payload", async () => {
    const result = await generateJson({ key: "value" });

    expect(result).toHaveProperty("output_json");
    expect(result.output_json).toMatchObject({
      summary: "Data extracted successfully",
      rows: [{ id: 1, value: "test" }],
    });
  });

  it("sends custom_schema_id when one is selected", async () => {
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      output_json: { summary: "Data extracted successfully", rows: [{ id: 1, value: "test" }] },
    });

    await generateJson(
      { key: "value" },
      "11111111-1111-1111-1111-111111111111"
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      "llm/generate/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          input_json: { key: "value" },
          custom_schema_id: "11111111-1111-1111-1111-111111111111",
        }),
        headers: {
          "Content-Type": "application/json",
        },
      })
    );
    fetchSpy.mockRestore();
  });

  it("adds bearer authorization when an access token exists even without a custom schema", async () => {
    mockGetStoredAccessToken.mockReturnValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      output_json: { summary: "Data extracted successfully", rows: [{ id: 1, value: "test" }] },
    });

    await generateJson({ key: "value" });

    expect(fetchSpy).toHaveBeenCalledWith(
      "llm/generate/",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
      })
    );

    fetchSpy.mockRestore();
  });

  it("adds bearer authorization when an access token exists and a custom schema is selected", async () => {
    mockGetStoredAccessToken.mockReturnValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      output_json: { summary: "Data extracted successfully", rows: [{ id: 1, value: "test" }] },
    });

    await generateJson(
      { key: "value" },
      "11111111-1111-1111-1111-111111111111"
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      "llm/generate/",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
      })
    );

    fetchSpy.mockRestore();
  });
});

describe("generateJson negative (HTTP errors)", () => {
  beforeEach(() => {
    mockGetStoredAccessToken.mockReturnValue(null);
  });

  it("maps 401 to user-friendly message", async () => {
    server.use(handler401);
    await expect(generateJson({ key: "value" })).rejects.toThrow("Invalid API key.");
  });

  it("maps 429 to user-friendly message", async () => {
    server.use(handler429);
    await expect(generateJson({ key: "value" })).rejects.toThrow(
      "Rate limit exceeded. Please try again later."
    );
  });

  it("maps 504 to user-friendly message", async () => {
    server.use(handler504);
    await expect(generateJson({ key: "value" })).rejects.toThrow(
      "Request timed out. Please try again."
    );
  });

  it("maps 503 to user-friendly message", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ detail: "Service Unavailable" }, { status: 503 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow(
      "Service is currently unavailable. Please try again later."
    );
  });

  it("keeps original API error when status is not mapped", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ detail: "Teapot" }, { status: 418 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow("Request failed. Please try again.");
  });

  it("supports legacy message-based API errors without a status property", async () => {
    const fetchSpy = vi
      .spyOn(api, "fetchAPI")
      .mockRejectedValue(new Error("API error: 429"));

    await expect(generateJson({ key: "value" })).rejects.toThrow(
      "Rate limit exceeded. Please try again later."
    );

    fetchSpy.mockRestore();
  });
});

describe("generateJson edge cases", () => {
  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    mockGetStoredAccessToken.mockReturnValue(null);
  });

  it("throws validation error for empty input", async () => {
    await expect(generateJson({})).rejects.toThrow("Input cannot be empty.");
  });

  it("throws validation error for empty array input", async () => {
    await expect(generateJson([])).rejects.toThrow("Input cannot be empty.");
  });

  it("throws schema error when output_json is missing", async () => {
    server.use(handlerInvalidSchema);
    await expect(generateJson({ key: "value" })).rejects.toThrow("The server returned an invalid response.");
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

  beforeEach(() => {
    mockGetStoredAccessToken.mockReturnValue(null);
  });

  it("throws schema error when output_json is an array", async () => {
    server.use(handlerArrayOutput);
    await expect(generateJson({ key: "value" })).rejects.toThrow("The server returned an invalid response.");
  });

  it("throws schema error when output_json is a primitive string", async () => {
    server.use(handlerPrimitiveOutput);
    await expect(generateJson({ key: "value" })).rejects.toThrow("The server returned an invalid response.");
  });

  it("throws schema error when output_json is a primitive number", async () => {
    server.use(
      http.post(`${API_BASE}/llm/generate/`, () =>
        HttpResponse.json({ output_json: 42 }, { status: 200 })
      )
    );
    await expect(generateJson({ key: "value" })).rejects.toThrow("The server returned an invalid response.");
  });
});

describe("exportToCsv", () => {
  const mockJson = { status: "ok" };

  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
  });

  it("returns file_id on successful export", async () => {
    server.use(exportCsvSuccessHandler);
    const result = await exportToCsv(mockJson);
    expect(result).toEqual({ file_id: "csv_12345" });
  });

  it("throws error if response does not contain file_id", async () => {
    server.use(exportCsvInvalidSchemaHandler);
    await expect(exportToCsv(mockJson)).rejects.toThrow("The CSV export response is invalid.");
  });

  it("throws error if file_id does not have 'csv_' prefix", async () => {
    server.use(exportCsvInvalidPrefixHandler);
    await expect(exportToCsv(mockJson)).rejects.toThrow("The CSV export response is invalid.");
  });

  it("maps HTTP errors properly using existing ERROR_MESSAGES", async () => {
    server.use(
      http.post(`${API_BASE}/export/csv`, () =>
        HttpResponse.json({ detail: "Gateway Timeout" }, { status: 504 })
      )
    );
    await expect(exportToCsv(mockJson)).rejects.toThrow(
      "Request timed out. Please try again."
    );
  });

  it("passes through unmapped HTTP errors", async () => {
    server.use(
      http.post(`${API_BASE}/export/csv`, () =>
        HttpResponse.json({ detail: "Teapot" }, { status: 418 })
      )
    );
    await expect(exportToCsv(mockJson)).rejects.toThrow("Request failed. Please try again.");
  });

  it("supports legacy message-based API errors without a status property", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("API error: 504"));

    await expect(exportToCsv(mockJson)).rejects.toThrow(
      "Request timed out. Please try again."
    );
  });

  it("passes through unknown errors from fetchAPI", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("Unknown Failure"));
    await expect(exportToCsv(mockJson)).rejects.toThrow("Unknown Failure");
  });

  it("passes through non-Error rejections", async () => {
    vi.spyOn(api, "fetchAPI").mockRejectedValue("String Failure");
    await expect(exportToCsv(mockJson)).rejects.toBe("String Failure");
  });

  it("sends bearer authorization for csv export", async () => {
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      file_id: "csv_12345",
    });

    await exportToCsv(mockJson);

    expect(fetchSpy).toHaveBeenCalledWith("export/csv", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer access-token",
      },
      body: JSON.stringify({ output_json: mockJson }),
    });
  });

  it("fails before export request when no access token is available", async () => {
    mockGetValidAccessToken.mockResolvedValue(null);
    const fetchSpy = vi.spyOn(api, "fetchAPI");

    await expect(exportToCsv(mockJson)).rejects.toThrow(
      "Authentication credentials were not provided."
    );

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("exportToExcel", () => {
  const mockJson = { status: "ok" };

  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  it("returns trusted excel metadata on successful export", async () => {
    server.use(exportExcelSuccessHandler);
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");

    const result = await excelService.exportToExcel(mockJson);

    expect(result).toEqual({
      file_id: "xlsx_12345",
      file_name: "export_12345.xlsx",
      artifact_type: "xlsx",
    });
  });

  it("throws error if response does not contain required excel metadata", async () => {
    server.use(exportExcelInvalidSchemaHandler);
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "The Excel export response is invalid."
    );
  });

  it("throws error if the excel export response is null", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue(null);

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "The Excel export response is invalid."
    );
  });

  it("throws error if file_id does not have 'xlsx_' prefix", async () => {
    server.use(exportExcelInvalidPrefixHandler);
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "The Excel export response is invalid."
    );
  });

  it("throws error if artifact_type is not xlsx", async () => {
    server.use(exportExcelInvalidArtifactTypeHandler);
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "The Excel export response is invalid."
    );
  });

  it("throws error if file_name is not an xlsx filename", async () => {
    server.use(exportExcelInvalidFileNameHandler);
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "The Excel export response is invalid."
    );
  });

  it("maps HTTP errors properly using existing ERROR_MESSAGES", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    server.use(
      http.post(`${API_BASE}/export/excel`, () =>
        HttpResponse.json({ detail: "Service Unavailable" }, { status: 503 })
      )
    );

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Service is currently unavailable. Please try again later."
    );
  });

  it("maps API errors that expose a numeric status property", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const errorWithStatus = Object.assign(new Error("Service Unavailable"), {
      status: 503,
    });
    vi.spyOn(api, "fetchAPI").mockRejectedValue(errorWithStatus);

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Service is currently unavailable. Please try again later."
    );
  });

  it("supports legacy message-based API errors without a status property", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("API error: 503"));

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Service is currently unavailable. Please try again later."
    );
  });

  it("passes through unknown errors from fetchAPI", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockRejectedValue(new Error("Unknown Failure"));

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Unknown Failure"
    );
  });

  it("passes through numeric status errors when no mapped user message exists", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const unmappedStatusError = Object.assign(new Error("Teapot"), {
      status: 418,
    });
    vi.spyOn(api, "fetchAPI").mockRejectedValue(unmappedStatusError);

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Teapot"
    );
  });

  it("passes through non-Error rejections", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockRejectedValue("String Failure");

    await expect(excelService.exportToExcel(mockJson)).rejects.toBe(
      "String Failure"
    );
  });

  it("sends bearer authorization for excel export", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      file_id: "xlsx_12345",
      file_name: "export_12345.xlsx",
      artifact_type: "xlsx",
    });

    await excelService.exportToExcel(mockJson);

    expect(fetchSpy).toHaveBeenCalledWith("export/excel", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer access-token",
      },
      body: JSON.stringify({ output_json: mockJson }),
    });
  });

  it("fails before export request when no access token is available", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue(null);
    const fetchSpy = vi.spyOn(api, "fetchAPI");

    await expect(excelService.exportToExcel(mockJson)).rejects.toThrow(
      "Authentication credentials were not provided."
    );

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("downloadExcelFile", () => {
  const originalCreateElement = document.createElement.bind(document);
  const createSuccessfulDownloadResponse = () =>
    ({
      ok: true,
      status: 200,
      headers: new Headers({
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
      blob: vi.fn().mockResolvedValue(new Blob(["excel-bytes"])),
    }) as unknown as Response;

  const createFailedDownloadResponse = (status: number) =>
    ({
      ok: false,
      status,
      headers: new Headers(),
      blob: vi.fn(),
    }) as unknown as Response;

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("downloads the excel file from the excel download endpoint", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(createSuccessfulDownloadResponse());
    vi.stubGlobal("fetch", fetchMock);

    const createObjectURL = vi.fn().mockReturnValue("blob:excel-file");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectURL,
    });

    const anchor = originalCreateElement("a");
    const clickSpy = vi.spyOn(anchor, "click").mockImplementation(() => { });
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      if (tagName.toLowerCase() === "a") {
        return anchor;
      }

      return originalCreateElement(tagName);
    });

    const appendSpy = vi
      .spyOn(document.body, "appendChild")
      .mockImplementation((node: Node) => node);
    const removeSpy = vi
      .spyOn(anchor, "remove")
      .mockImplementation(() => { });

    await excelService.downloadExcelFile("xlsx_12345", "report.xlsx");

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/export/excel/xlsx_12345/download`,
      {
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      }
    );
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchor.download).toBe("report.xlsx");
    expect(anchor.href).toBe("blob:excel-file");
    expect(appendSpy).toHaveBeenCalledWith(anchor);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(removeSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:excel-file");
  });

  it("rejects invalid excel file ids before requesting download", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      excelService.downloadExcelFile("csv_12345", "report.xlsx")
    ).rejects.toThrow("The Excel download request is invalid.");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws a normalized error when the download response is not ok", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi.fn().mockResolvedValue(createFailedDownloadResponse(500));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      excelService.downloadExcelFile("xlsx_12345", "report.xlsx")
    ).rejects.toThrow("Failed to export");
  });

  it("throws a normalized error when the network request fails", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi.fn().mockRejectedValue(new Error("Network down"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      excelService.downloadExcelFile("xlsx_12345", "report.xlsx")
    ).rejects.toThrow("Failed to export");
  });

  it("rethrows invalid download request errors without normalizing them", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi
      .fn()
      .mockRejectedValue(new Error("The Excel download request is invalid."));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      excelService.downloadExcelFile("xlsx_12345", "report.xlsx")
    ).rejects.toThrow("The Excel download request is invalid.");
  });

  it("cleans up object urls if browser download setup fails unexpectedly", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(createSuccessfulDownloadResponse());
    vi.stubGlobal("fetch", fetchMock);

    const createObjectURL = vi.fn().mockReturnValue("blob:excel-file");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectURL,
    });

    vi.spyOn(document, "createElement").mockImplementation(() => {
      throw new Error("Anchor creation failed");
    });

    await expect(
      excelService.downloadExcelFile("xlsx_12345", "report.xlsx")
    ).rejects.toThrow("Failed to export");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:excel-file");
  });

  it("fails before download request when no access token is available", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      excelService.downloadExcelFile("xlsx_12345", "report.xlsx")
    ).rejects.toThrow("Authentication credentials were not provided.");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("downloadCsvFile", () => {
  const originalCreateElement = document.createElement.bind(document);
  const createSuccessfulDownloadResponse = () =>
    ({
      ok: true,
      status: 200,
      headers: new Headers({
        "Content-Type": "text/csv",
      }),
      blob: vi.fn().mockResolvedValue(new Blob(["csv-bytes"])),
    }) as unknown as Response;

  const createFailedDownloadResponse = (status: number) =>
    ({
      ok: false,
      status,
      headers: new Headers(),
      blob: vi.fn(),
    }) as unknown as Response;

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("downloads the csv file from the csv download endpoint with bearer auth", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi.fn().mockResolvedValue(createSuccessfulDownloadResponse());
    vi.stubGlobal("fetch", fetchMock);

    const createObjectURL = vi.fn().mockReturnValue("blob:csv-file");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: revokeObjectURL,
    });

    const anchor = originalCreateElement("a");
    const clickSpy = vi.spyOn(anchor, "click").mockImplementation(() => {});
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      if (tagName.toLowerCase() === "a") {
        return anchor;
      }

      return originalCreateElement(tagName);
    });

    const appendSpy = vi
      .spyOn(document.body, "appendChild")
      .mockImplementation((node: Node) => node);
    const removeSpy = vi.spyOn(anchor, "remove").mockImplementation(() => {});

    await downloadCsvFile("csv_12345", "report.csv");

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/export/csv/csv_12345/download?filename=report.csv`,
      {
        method: "GET",
        headers: {
          Authorization: "Bearer access-token",
        },
      }
    );
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchor.download).toBe("report.csv");
    expect(anchor.href).toBe("blob:csv-file");
    expect(appendSpy).toHaveBeenCalledWith(anchor);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(removeSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:csv-file");
  });

  it("throws a normalized error when the csv download response is not ok", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue("access-token");
    const fetchMock = vi.fn().mockResolvedValue(createFailedDownloadResponse(500));
    vi.stubGlobal("fetch", fetchMock);

    await expect(downloadCsvFile("csv_12345", "report.csv")).rejects.toThrow(
      "Failed to export"
    );
  });

  it("fails before csv download request when no access token is available", async () => {
    vi.spyOn(auth, "getValidAccessToken").mockResolvedValue(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(downloadCsvFile("csv_12345", "report.csv")).rejects.toThrow(
      "Authentication credentials were not provided."
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("getDownloadUrl", () => {
  it("returns a valid download URL without filename", () => {
    const url = getDownloadUrl("csv_abc");
    expect(url).toBe(`${API_BASE}/export/csv/csv_abc/download`);
  });

  it("appends and URI-encodes the filename parameter", () => {
    const url = getDownloadUrl("csv_abc", "laporan keuangan 2024.csv");
    expect(url).toBe(`${API_BASE}/export/csv/csv_abc/download?filename=laporan%20keuangan%202024.csv`);
  });

  it("falls back to localhost:8000 if URL parsing fails", () => {
    const original = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = "htt   p://in^valid\nurl";

    const url = getDownloadUrl("csv_abc");
    expect(url).toBe("http://localhost:8000/export/csv/csv_abc/download");

    process.env.NEXT_PUBLIC_API_URL = original;
  });

  it("uses localhost:8000 when NEXT_PUBLIC_API_URL is unset", () => {
    const original = process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;

    const url = getDownloadUrl("csv_abc");
    expect(url).toBe("http://localhost:8000/export/csv/csv_abc/download");

    process.env.NEXT_PUBLIC_API_URL = original;
  });
});
