import { fetchAPI } from "@/lib/api";
import { getValidAccessToken } from "@/lib/auth";

export interface HistoryItem {
  id: string;
  original_name: string;
  custom_name: string;
  status_processing: string;
  created_at: string;
}

export interface HistoryListResponse {
  count: number;
  limit: number;
  offset: number;
  results: HistoryItem[];
}

const HISTORY_DOWNLOAD_ERROR_MESSAGE = "Failed to download history file.";

function getApiBaseOrigin(): string {
  try {
    return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").origin;
  } catch {
    return "http://localhost:8000";
  }
}

function isValidHistoryListResponse(data: unknown): data is HistoryListResponse {
  if (typeof data !== "object" || data === null) {
    return false;
  }

  const response = data as Record<string, unknown>;
  return (
    typeof response.count === "number" &&
    typeof response.limit === "number" &&
    typeof response.offset === "number" &&
    Array.isArray(response.results)
  );
}

function assertValidHistoryPagination(limit: number, offset: number): void {
  if (!Number.isInteger(limit) || limit <= 0) {
    throw new Error("The history request is invalid.");
  }

  if (!Number.isInteger(offset) || offset < 0) {
    throw new Error("The history request is invalid.");
  }
}

function assertValidHistoryDownloadFormat(fileFormat: string): void {
  if (fileFormat !== "csv" && fileFormat !== "xlsx") {
    throw new Error("The history download request is invalid.");
  }
}

function cleanupDownloadResources(
  downloadAnchor: HTMLAnchorElement | null,
  objectUrl: string | null,
  appendedToBody: boolean
): void {
  if (downloadAnchor && appendedToBody) {
    downloadAnchor.remove();
  }

  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
  }
}

export async function getHistoryFiles(
  limit = 10,
  offset = 0
): Promise<HistoryListResponse> {
  assertValidHistoryPagination(limit, offset);

  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  const data = await fetchAPI(`history/?limit=${limit}&offset=${offset}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!isValidHistoryListResponse(data)) {
    throw new Error("The history response is invalid.");
  }

  return data;
}

export async function downloadHistoryFile(
  historyId: string,
  fileFormat: "csv" | "xlsx",
  filename?: string
): Promise<void> {
  assertValidHistoryDownloadFormat(fileFormat);

  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  let objectUrl: string | null = null;
  let downloadAnchor: HTMLAnchorElement | null = null;
  let appendedToBody = false;

  try {
    const response = await fetch(
      `${getApiBaseOrigin()}/history/${historyId}/download/?file_format=${fileFormat}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(HISTORY_DOWNLOAD_ERROR_MESSAGE);
    }

    const blob = await response.blob();
    objectUrl = URL.createObjectURL(blob);

    downloadAnchor = document.createElement("a");
    downloadAnchor.href = objectUrl;
    downloadAnchor.download = filename || `history-export.${fileFormat}`;
    document.body.appendChild(downloadAnchor);
    appendedToBody = true;
    downloadAnchor.click();
  } catch {
    throw new Error(HISTORY_DOWNLOAD_ERROR_MESSAGE);
  } finally {
    cleanupDownloadResources(downloadAnchor, objectUrl, appendedToBody);
  }
}
