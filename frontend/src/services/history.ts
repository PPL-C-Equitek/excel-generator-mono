import { fetchAPI } from "@/lib/api";
import { getValidAccessToken } from "@/lib/auth";
import { resolveDownloadFilename } from "@/utils/downloadFilename";

export interface HistoryItem {
  id: string;
  original_name: string;
  custom_name: string;
  session_id?: string | null;
  status_processing: string;
  created_at: string;
}

export interface HistoryListResponse {
  count: number;
  limit: number;
  offset: number;
  results: HistoryItem[];
}

interface SessionListItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  last_output_at: string | null;
}

interface SessionListResponse {
  count: number;
  limit: number;
  offset: number;
  results: SessionListItem[];
}

const HISTORY_DOWNLOAD_ERROR_MESSAGE = "Failed to download file.";
const HISTORY_RENAME_ERROR_MESSAGE = "Failed to rename history item.";
const HISTORY_DELETE_ERROR_MESSAGE = "Failed to delete history item.";

function getHistoryDownloadErrorMessage(status: number): string {
  if (status === 401 || status === 403) {
    return "Your session is invalid or you no longer have access.";
  }

  if (status === 404) {
    return "This history item could not be found.";
  }

  if (status === 400) {
    return "The history download request is invalid.";
  }

  if (status >= 500) {
    return "Failed to download due to a server error.";
  }

  return HISTORY_DOWNLOAD_ERROR_MESSAGE;
}

function isHistoryDownloadMappedError(message: string): boolean {
  return (
    message === "Your session is invalid or you no longer have access." ||
    message === "This history item could not be found." ||
    message === "The history download request is invalid." ||
    message === "Failed to download due to a server error." ||
    message === HISTORY_DOWNLOAD_ERROR_MESSAGE
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readStringField(data: unknown, field: string): string | null {
  if (!isRecord(data)) {
    return null;
  }

  const value = data[field];
  return typeof value === "string" ? value : null;
}

function findFirstString(values: unknown[]): string | null {
  const firstString = values.find((value) => typeof value === "string");
  return typeof firstString === "string" ? firstString : null;
}

function readNestedString(data: unknown): string | null {
  if (!isRecord(data)) {
    return null;
  }

  for (const value of Object.values(data)) {
    if (typeof value === "string") {
      return value;
    }

    if (Array.isArray(value)) {
      const nestedString = findFirstString(value);
      if (nestedString) {
        return nestedString;
      }
    }
  }

  return null;
}

function readHistoryErrorMessage(data: unknown, fallback: string): string {
  return (
    readStringField(data, "message") ??
    readStringField(data, "detail") ??
    (Array.isArray(data) ? findFirstString(data) : null) ??
    readNestedString(data) ??
    fallback
  );
}

function getApiBaseOrigin(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
}

function buildHistoryApiUrl(path: string): string {
  const normalizedPath = path.replace(/^\/+/, "");
  return `${getApiBaseOrigin()}/${normalizedPath}`;
}

function buildHistoryDownloadUrl(
  historyId: string,
  fileFormat: "csv" | "xlsx",
  filename: string
): string {
  const params = new URLSearchParams({
    file_format: fileFormat,
    filename,
  });

  return buildHistoryApiUrl(`history/${historyId}/download/?${params.toString()}`);
}

function isValidHistoryItem(data: unknown): data is HistoryItem {
  if (!isRecord(data)) {
    return false;
  }

  return (
    typeof data.id === "string" &&
    typeof data.original_name === "string" &&
    typeof data.custom_name === "string" &&
    (data.session_id === undefined ||
      data.session_id === null ||
      typeof data.session_id === "string") &&
    typeof data.status_processing === "string" &&
    typeof data.created_at === "string"
  );
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

function isValidSessionListItem(data: unknown): data is SessionListItem {
  if (!isRecord(data)) {
    return false;
  }

  return (
    typeof data.id === "string" &&
    typeof data.title === "string" &&
    typeof data.created_at === "string" &&
    typeof data.updated_at === "string" &&
    (typeof data.last_message_at === "string" || data.last_message_at === null) &&
    (typeof data.last_output_at === "string" || data.last_output_at === null)
  );
}

function isValidSessionListResponse(data: unknown): data is SessionListResponse {
  if (!isRecord(data)) {
    return false;
  }

  return (
    typeof data.count === "number" &&
    typeof data.limit === "number" &&
    typeof data.offset === "number" &&
    Array.isArray(data.results) &&
    data.results.every(isValidSessionListItem)
  );
}

function mapSessionToHistoryItem(session: SessionListItem): HistoryItem {
  return {
    id: session.id,
    original_name: session.title,
    custom_name: "",
    session_id: session.id,
    status_processing: "completed",
    created_at:
      session.last_output_at ??
      session.last_message_at ??
      session.updated_at ??
      session.created_at,
  };
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

function getHistoryActionErrorMessage(
  status: number,
  fallback: string
): string {
  if (status === 401 || status === 403) {
    return "Your session is invalid or you no longer have access.";
  }

  if (status === 404) {
    return "This history item could not be found.";
  }

  if (status === 400) {
    return "The history request is invalid.";
  }

  if (status >= 500) {
    return fallback;
  }

  return fallback;
}

async function requestHistoryApi<T>(
  path: string,
  accessToken: string,
  options?: RequestInit,
  fallbackErrorMessage = "Request failed."
): Promise<T> {
  const headers = new Headers(options?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);

  if (options?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildHistoryApiUrl(path), {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      readHistoryErrorMessage(
        data,
        getHistoryActionErrorMessage(response.status, fallbackErrorMessage)
      )
    );
  }

  return data as T;
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

  const data = await fetchAPI(`sessions/?limit=${limit}&offset=${offset}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!isValidSessionListResponse(data)) {
    throw new Error("The sessions response is invalid.");
  }

  return {
    count: data.count,
    limit: data.limit,
    offset: data.offset,
    results: data.results.map(mapSessionToHistoryItem),
  };
}

export async function downloadHistoryFile(
  historyId: string,
  fileFormat: "csv" | "xlsx",
  filename?: string
): Promise<void> {
  assertValidHistoryDownloadFormat(fileFormat);
  const requestedFilename =
    typeof filename === "string" && filename.trim().length > 0
      ? filename
      : `history-export.${fileFormat}`;

  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  let objectUrl: string | null = null;
  let downloadAnchor: HTMLAnchorElement | null = null;
  let appendedToBody = false;

  try {
    const response = await fetch(
      buildHistoryDownloadUrl(historyId, fileFormat, requestedFilename),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(getHistoryDownloadErrorMessage(response.status));
    }

    const blob = await response.blob();
    const downloadFilename = resolveDownloadFilename(
      response.headers,
      requestedFilename
    );
    objectUrl = URL.createObjectURL(blob);

    downloadAnchor = document.createElement("a");
    downloadAnchor.href = objectUrl;
    downloadAnchor.download = downloadFilename;
    document.body.appendChild(downloadAnchor);
    appendedToBody = true;
    downloadAnchor.click();
  } catch (error) {
    if (error instanceof Error && isHistoryDownloadMappedError(error.message)) {
      throw error;
    }

    throw new Error(HISTORY_DOWNLOAD_ERROR_MESSAGE);
  } finally {
    cleanupDownloadResources(downloadAnchor, objectUrl, appendedToBody);
  }
}

export async function renameHistoryFile(
  historyId: string,
  customName: string
): Promise<HistoryItem> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  const data = await requestHistoryApi<unknown>(
    `sessions/${historyId}/`,
    accessToken,
    {
      method: "PATCH",
      body: JSON.stringify({ title: customName }),
    },
    HISTORY_RENAME_ERROR_MESSAGE
  );

  if (!isValidSessionListItem(data)) {
    throw new Error("The history response is invalid.");
  }

  return mapSessionToHistoryItem(data);
}

export async function deleteHistoryFile(historyId: string): Promise<void> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  await requestHistoryApi<void>(
    `sessions/${historyId}/`,
    accessToken,
    {
      method: "DELETE",
    },
    HISTORY_DELETE_ERROR_MESSAGE
  );
}
