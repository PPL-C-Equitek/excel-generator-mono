import { fetchAPI } from "@/lib/api";
import { getStoredAccessToken, getValidAccessToken } from "@/lib/auth";
import { ERROR_MESSAGES } from "@/constants/errorMessages";
import { resolveDownloadFilename } from "@/utils/downloadFilename";
import { isJsonObject } from "@/utils/schemaValidator";
import type { JsonValue } from "@/utils/schemaValidator";
export { ERROR_MESSAGES } from "@/constants/errorMessages";
export type { JsonValue } from "@/utils/schemaValidator";

export interface LLMRequest {
  input_json: JsonValue;
  custom_schema_id?: string;
}

export interface LLMResponse {
  output_json: JsonValue;
}

export interface ExcelExportResponse {
  file_id: string;
  file_name: string;
  artifact_type: "xlsx";
}

const EXCEL_EXPORT_ERROR_MESSAGE = "The Excel export response is invalid.";
const EXCEL_DOWNLOAD_ERROR_MESSAGE = "Failed to export";
const CSV_DOWNLOAD_ERROR_MESSAGE = "Failed to export";
const AUTH_MISSING_ERROR_MESSAGE = "Authentication credentials were not provided.";
const DEFAULT_API_ERROR_MESSAGE = "Request failed. Please try again.";
const INVALID_EXCEL_DOWNLOAD_ERROR_MESSAGE =
  "The Excel download request is invalid.";

type AuthTokenSource = "stored-optional" | "valid";
type ApiErrorFallbackMode = "mapped-only" | "mapped-or-default";
type AuthTokenResolver = () => string | null | Promise<string | null>;

const AUTH_TOKEN_RESOLVERS: Record<AuthTokenSource, AuthTokenResolver> = {
  "stored-optional": getStoredAccessToken,
  valid: getValidAccessToken,
};

function buildJsonRequestHeaders(accessToken: string | null): HeadersInit {
  if (!accessToken) {
    return {
      "Content-Type": "application/json",
    };
  }

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
  };
}

function getErrorStatus(err: Error): number | null {
  const errorWithStatus = err as Error & { status?: number };
  if (typeof errorWithStatus.status === "number") {
    return errorWithStatus.status;
  }

  const statusMatch = /API error: (\d+)/.exec(err.message);
  if (statusMatch) {
    return Number.parseInt(statusMatch[1], 10);
  }

  return null;
}

function rethrowMappedApiError(err: unknown): never {
  if (err instanceof Error) {
    const status = getErrorStatus(err);
    if (status !== null) {
      const userMessage = ERROR_MESSAGES[status];
      if (userMessage) {
        throw new Error(userMessage);
      }
    }
  }

  throw err;
}

function rethrowMappedApiErrorWithDefault(err: unknown): never {
  if (err instanceof Error) {
    const status = getErrorStatus(err);
    if (status !== null) {
      const userMessage = ERROR_MESSAGES[status];
      if (userMessage) {
        throw new Error(userMessage);
      }

      throw new Error(DEFAULT_API_ERROR_MESSAGE);
    }
  }

  throw err;
}

async function getAuthToken(source: AuthTokenSource): Promise<string | null> {
  const tokenValue = AUTH_TOKEN_RESOLVERS[source]();
  return tokenValue instanceof Promise ? await tokenValue : tokenValue;
}

async function postJsonRequest(
  endpoint: string,
  body: unknown,
  options: {
    authSource?: AuthTokenSource;
    signal?: AbortSignal;
    errorMode?: ApiErrorFallbackMode;
  } = {}
): Promise<unknown> {
  const authSource = options.authSource ?? "stored-optional";
  const accessToken = await getAuthToken(authSource);

  if (authSource === "valid" && !accessToken) {
    throw new Error(AUTH_MISSING_ERROR_MESSAGE);
  }

  const requestOptions: RequestInit = {
    method: "POST",
    headers: buildJsonRequestHeaders(accessToken),
    body: JSON.stringify(body),
  };

  if (options.signal) {
    requestOptions.signal = options.signal;
  }

  try {
    return await fetchAPI(endpoint, requestOptions);
  } catch (err: unknown) {
    if ((options.errorMode ?? "mapped-only") === "mapped-or-default") {
      rethrowMappedApiErrorWithDefault(err);
    }

    rethrowMappedApiError(err);
  }
}

export async function generateJson(
  inputJson: JsonValue,
  customSchemaId?: string | null,
  signal?: AbortSignal
): Promise<LLMResponse> {
  const isEmpty = Array.isArray(inputJson)
    ? inputJson.length === 0
    : Object.keys(inputJson).length === 0;

  if (isEmpty) {
    throw new Error("Input cannot be empty.");
  }

  const requestBody: LLMRequest = { input_json: inputJson };
  if (typeof customSchemaId === "string" && customSchemaId.trim().length > 0) {
    requestBody.custom_schema_id = customSchemaId;
  }

  const data = await postJsonRequest("llm/generate/", requestBody, {
    signal,
    errorMode: "mapped-or-default",
  });

  if (
    typeof data !== "object" ||
    data === null ||
    !("output_json" in data) ||
    !isJsonObject((data as Record<string, unknown>)["output_json"])
  ) {
    throw new Error("The server returned an invalid response.");
  }

  return data as LLMResponse;
}

function getApiBaseOrigin(): string {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  let endIndex = apiBaseUrl.length;

  while (endIndex > 0 && apiBaseUrl[endIndex - 1] === "/") {
    endIndex -= 1;
  }

  return apiBaseUrl.slice(0, endIndex);
}

function isValidExcelExportResponse(data: unknown): data is ExcelExportResponse {
  if (typeof data !== "object" || data === null) {
    return false;
  }

  const response = data as Record<string, unknown>;
  return (
    typeof response.file_id === "string" &&
    response.file_id.startsWith("xlsx_") &&
    typeof response.file_name === "string" &&
    response.file_name.endsWith(".xlsx") &&
    response.artifact_type === "xlsx"
  );
}

function assertValidExcelDownloadFileId(fileId: string): void {
  if (typeof fileId !== "string" || !fileId.startsWith("xlsx_")) {
    throw new Error(INVALID_EXCEL_DOWNLOAD_ERROR_MESSAGE);
  }
}

function cleanupBlobDownloadResources(
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

async function downloadBlobFileFromUrl(
  requestUrl: string,
  filename: string,
  options: {
    requestErrorMessage: string;
    passThroughInvalidFileIdError?: boolean;
  }
): Promise<void> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error(AUTH_MISSING_ERROR_MESSAGE);
  }

  let objectUrl: string | null = null;
  let downloadAnchor: HTMLAnchorElement | null = null;
  let appendedToBody = false;

  try {
    const response = await fetch(requestUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error(options.requestErrorMessage);
    }

    const blob = await response.blob();
    const downloadFilename = resolveDownloadFilename(response.headers, filename);
    objectUrl = URL.createObjectURL(blob);

    downloadAnchor = document.createElement("a");
    downloadAnchor.href = objectUrl;
    downloadAnchor.download = downloadFilename;
    document.body.appendChild(downloadAnchor);
    appendedToBody = true;
    downloadAnchor.click();
  } catch (err: unknown) {
    if (
      options.passThroughInvalidFileIdError &&
      err instanceof Error &&
      err.message === INVALID_EXCEL_DOWNLOAD_ERROR_MESSAGE
    ) {
      throw err;
    }

    throw new Error(options.requestErrorMessage);
  } finally {
    cleanupBlobDownloadResources(downloadAnchor, objectUrl, appendedToBody);
  }
}

export async function exportToCsv(
  outputJson: JsonValue,
  signal?: AbortSignal
): Promise<{ file_id: string }> {
  const data = await postJsonRequest(
    "export/csv",
    {
      output_json: outputJson,
    },
    {
      authSource: "valid",
      signal,
      errorMode: "mapped-or-default",
    }
  );

  if (
    typeof data !== "object" ||
    data === null ||
    !("file_id" in data) ||
    typeof (data as Record<string, unknown>).file_id !== "string" ||
    !(data as Record<string, string>).file_id.startsWith("csv_")
  ) {
    throw new Error("The CSV export response is invalid.");
  }

  return { file_id: (data as Record<string, string>).file_id };
}

export async function downloadCsvFile(
  fileId: string,
  filename = "export.csv"
): Promise<void> {
  await downloadBlobFileFromUrl(
    getDownloadUrl(fileId, filename),
    filename,
    {
      requestErrorMessage: CSV_DOWNLOAD_ERROR_MESSAGE,
    }
  );
}

export async function exportToExcel(
  outputJson: JsonValue,
  signal?: AbortSignal
): Promise<ExcelExportResponse> {
  const data = await postJsonRequest(
    "export/excel",
    {
      output_json: outputJson,
    },
    {
      authSource: "valid",
      signal,
    }
  );

  if (!isValidExcelExportResponse(data)) {
    throw new Error(EXCEL_EXPORT_ERROR_MESSAGE);
  }

  return {
    file_id: data.file_id,
    file_name: data.file_name,
    artifact_type: data.artifact_type,
  };
}

export async function downloadExcelFile(
  fileId: string,
  filename = "export.xlsx"
): Promise<void> {
  assertValidExcelDownloadFileId(fileId);

  await downloadBlobFileFromUrl(
    `${getApiBaseOrigin()}/export/excel/${fileId}/download`,
    filename,
    {
      requestErrorMessage: EXCEL_DOWNLOAD_ERROR_MESSAGE,
      passThroughInvalidFileIdError: true,
    }
  );
}

export function getDownloadUrl(fileId: string, filename?: string): string {
  const base = getApiBaseOrigin();
  let url = `${base}/export/csv/${fileId}/download`;
  if (filename) {
    url += `?filename=${encodeURIComponent(filename)}`;
  }
  return url;
}
