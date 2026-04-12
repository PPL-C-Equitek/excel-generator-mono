import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import * as auth from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  getValidAccessToken: vi.fn(),
}));

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const mockGetValidAccessToken = vi.mocked(auth.getValidAccessToken);

describe("history service", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  describe("getHistoryFiles", () => {
    it("returns paginated history list for an authenticated user", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
        count: 1,
        limit: 10,
        offset: 0,
        results: [
          {
            id: "history-1",
            original_name: "invoice.pdf",
            custom_name: "",
            status_processing: "completed",
            created_at: "2026-04-10T13:00:00Z",
          },
        ],
      });

      const historyService = await import("@/services/history");
      const result = await historyService.getHistoryFiles(10, 0);

      expect(fetchSpy).toHaveBeenCalledWith("history/?limit=10&offset=0", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
      });
      expect(result).toEqual({
        count: 1,
        limit: 10,
        offset: 0,
        results: [
          {
            id: "history-1",
            original_name: "invoice.pdf",
            custom_name: "",
            status_processing: "completed",
            created_at: "2026-04-10T13:00:00Z",
          },
        ],
      });
    });

    it("returns an empty history list when the user has no history", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      vi.spyOn(api, "fetchAPI").mockResolvedValue({
        count: 0,
        limit: 10,
        offset: 0,
        results: [],
      });

      const historyService = await import("@/services/history");
      const result = await historyService.getHistoryFiles(10, 0);

      expect(result.results).toEqual([]);
      expect(result.count).toBe(0);
    });

    it("throws an authentication error when no access token is available", async () => {
      mockGetValidAccessToken.mockResolvedValue(null);
      const fetchSpy = vi.spyOn(api, "fetchAPI");

      const historyService = await import("@/services/history");

      await expect(historyService.getHistoryFiles(10, 0)).rejects.toThrow(
        "Authentication credentials were not provided."
      );
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("throws an error when the history list response shape is invalid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      vi.spyOn(api, "fetchAPI").mockResolvedValue({
        count: 1,
        limit: 10,
        offset: 0,
        results: "invalid-results",
      });

      const historyService = await import("@/services/history");

      await expect(historyService.getHistoryFiles(10, 0)).rejects.toThrow(
        "The history response is invalid."
      );
    });

    it("throws an error when the history list response is null", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      vi.spyOn(api, "fetchAPI").mockResolvedValue(null);

      const historyService = await import("@/services/history");

      await expect(historyService.getHistoryFiles(10, 0)).rejects.toThrow(
        "The history response is invalid."
      );
    });

    it("throws an error when pagination input is invalid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchSpy = vi.spyOn(api, "fetchAPI");

      const historyService = await import("@/services/history");

      await expect(historyService.getHistoryFiles(0, -1)).rejects.toThrow(
        "The history request is invalid."
      );
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("throws an error when offset is invalid even if limit is valid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchSpy = vi.spyOn(api, "fetchAPI");

      const historyService = await import("@/services/history");

      await expect(historyService.getHistoryFiles(10, -1)).rejects.toThrow(
        "The history request is invalid."
      );
      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });

  describe("downloadHistoryFile", () => {
    const originalCreateElement = document.createElement.bind(document);

    const createSuccessfulDownloadResponse = (contentType: string) =>
      ({
        ok: true,
        status: 200,
        headers: new Headers({
          "Content-Type": contentType,
        }),
        blob: vi.fn().mockResolvedValue(new Blob(["file-bytes"])),
      }) as unknown as Response;

    it("downloads a csv history file successfully", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi
        .fn()
        .mockResolvedValue(createSuccessfulDownloadResponse("text/csv"));
      vi.stubGlobal("fetch", fetchMock);

      const createObjectURL = vi.fn().mockReturnValue("blob:history-csv");
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

      const historyService = await import("@/services/history");
      await historyService.downloadHistoryFile("history-1", "csv", "invoice.csv");

      expect(fetchMock).toHaveBeenCalledWith(
        `${API_BASE}/history/history-1/download/?file_format=csv`,
        {
          method: "GET",
          headers: {
            Authorization: "Bearer access-token",
          },
        }
      );
      expect(anchor.download).toBe("invoice.csv");
      expect(appendSpy).toHaveBeenCalledWith(anchor);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(removeSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:history-csv");
    });

    it("downloads an xlsx history file successfully", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue(
        createSuccessfulDownloadResponse(
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
      );
      vi.stubGlobal("fetch", fetchMock);

      const createObjectURL = vi.fn().mockReturnValue("blob:history-xlsx");
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
      vi.spyOn(anchor, "click").mockImplementation(() => {});
      vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
        if (tagName.toLowerCase() === "a") {
          return anchor;
        }

        return originalCreateElement(tagName);
      });

      vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => node);
      vi.spyOn(anchor, "remove").mockImplementation(() => {});

      const historyService = await import("@/services/history");
      await historyService.downloadHistoryFile("history-1", "xlsx", "invoice.xlsx");

      expect(fetchMock).toHaveBeenCalledWith(
        `${API_BASE}/history/history-1/download/?file_format=xlsx`,
        {
          method: "GET",
          headers: {
            Authorization: "Bearer access-token",
          },
        }
      );
      expect(anchor.download).toBe("invoice.xlsx");
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:history-xlsx");
    });

    it("throws an authentication error when downloading without a token", async () => {
      mockGetValidAccessToken.mockResolvedValue(null);
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Authentication credentials were not provided.");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("throws an error when the download response is not ok", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Failed to download due to a server error.");
    });

    it("throws a specific auth error when the download response is 401", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Your session is invalid or you no longer have access.");
    });

    it("throws a specific not-found error when the download response is 404", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("This history item could not be found.");
    });

    it("throws a specific invalid-request error when the download response is 400", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("The history download request is invalid.");
    });

    it("throws a specific server error when the download response is 500", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Failed to download due to a server error.");
    });

    it("falls back to a generic error when the network request fails unexpectedly", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockRejectedValue(new Error("socket hang up"));
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Failed to download file.");
    });

    it("falls back to a generic error when the download response uses an unmapped status", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 418,
        headers: new Headers(),
        blob: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile("history-1", "csv", "invoice.csv")
      ).rejects.toThrow("Failed to download file.");
    });

    it("throws an error when fileFormat is invalid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.downloadHistoryFile(
          "history-1",
          "pdf" as "csv" | "xlsx",
          "invoice.pdf"
        )
      ).rejects.toThrow("The history download request is invalid.");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("uses the default filename when no filename is provided", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi
        .fn()
        .mockResolvedValue(createSuccessfulDownloadResponse("text/csv"));
      vi.stubGlobal("fetch", fetchMock);

      const createObjectURL = vi.fn().mockReturnValue("blob:history-csv");
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
      vi.spyOn(anchor, "click").mockImplementation(() => {});
      vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
        if (tagName.toLowerCase() === "a") {
          return anchor;
        }

        return originalCreateElement(tagName);
      });
      vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => node);
      vi.spyOn(anchor, "remove").mockImplementation(() => {});

      const historyService = await import("@/services/history");
      await historyService.downloadHistoryFile("history-1", "csv");

      expect(anchor.download).toBe("history-export.csv");
    });

    it("falls back to localhost:8000 when NEXT_PUBLIC_API_URL is invalid", async () => {
      const original = process.env.NEXT_PUBLIC_API_URL;
      process.env.NEXT_PUBLIC_API_URL = "htt   p://in^valid\nurl";

      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi
        .fn()
        .mockResolvedValue(createSuccessfulDownloadResponse("text/csv"));
      vi.stubGlobal("fetch", fetchMock);

      const createObjectURL = vi.fn().mockReturnValue("blob:history-csv");
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
      vi.spyOn(anchor, "click").mockImplementation(() => {});
      vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
        if (tagName.toLowerCase() === "a") {
          return anchor;
        }

        return originalCreateElement(tagName);
      });
      vi.spyOn(document.body, "appendChild").mockImplementation((node: Node) => node);
      vi.spyOn(anchor, "remove").mockImplementation(() => {});

      const historyService = await import("@/services/history");
      await historyService.downloadHistoryFile("history-1", "csv", "invoice.csv");

      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/history/history-1/download/?file_format=csv",
        {
          method: "GET",
          headers: {
            Authorization: "Bearer access-token",
          },
        }
      );

      process.env.NEXT_PUBLIC_API_URL = original;
    });
  });

  describe("renameHistoryFile", () => {
    it("renames a history item successfully", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          id: "history-1",
          original_name: "invoice.pdf",
          custom_name: "Renamed Invoice",
          status_processing: "completed",
          created_at: "2026-04-10T13:00:00Z",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");
      const result = await historyService.renameHistoryFile(
        "history-1",
        "Renamed Invoice"
      );

      expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/history/history-1/`, {
        method: "PATCH",
        headers: expect.any(Headers),
        body: JSON.stringify({ custom_name: "Renamed Invoice" }),
      });
      expect(result.custom_name).toBe("Renamed Invoice");
    });

    it("throws an authentication error when renaming without a token", async () => {
      mockGetValidAccessToken.mockResolvedValue(null);
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.renameHistoryFile("history-1", "Renamed Invoice")
      ).rejects.toThrow("Authentication credentials were not provided.");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("throws nested serializer errors when the rename request is invalid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: vi.fn().mockResolvedValue({
          custom_name: ["This field is required."],
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.renameHistoryFile("history-1", "Renamed Invoice")
      ).rejects.toThrow("This field is required.");
    });

    it("throws an error when the rename response shape is invalid", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          id: "history-1",
          custom_name: "Renamed Invoice",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(
        historyService.renameHistoryFile("history-1", "Renamed Invoice")
      ).rejects.toThrow("The history response is invalid.");
    });
  });

  describe("deleteHistoryFile", () => {
    it("deletes a history item successfully", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: vi.fn(),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");
      await historyService.deleteHistoryFile("history-1");

      expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/history/history-1/`, {
        method: "DELETE",
        headers: expect.any(Headers),
      });
    });

    it("throws an authentication error when deleting without a token", async () => {
      mockGetValidAccessToken.mockResolvedValue(null);
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(historyService.deleteHistoryFile("history-1")).rejects.toThrow(
        "Authentication credentials were not provided."
      );
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("throws a mapped not-found error when deleting a missing item", async () => {
      mockGetValidAccessToken.mockResolvedValue("access-token");
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: vi.fn().mockResolvedValue({
          message: "History item not found.",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const historyService = await import("@/services/history");

      await expect(historyService.deleteHistoryFile("history-1")).rejects.toThrow(
        "History item not found."
      );
    });
  });
});
