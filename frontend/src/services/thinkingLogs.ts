import { fetchAPI } from "@/lib/api";
import { getValidAccessToken } from "@/lib/auth";

export interface ThinkingLogItem {
  id: string;
  session_id: string | null;
  chat_id: string | null;
  thinking_log: string;
  reasoning: string[];
  status_processing: string;
  created_at: string;
}

export interface ThinkingLogListResponse {
  count: number;
  page: number;
  page_size: number;
  results: ThinkingLogItem[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isValidThinkingLogItem(value: unknown): value is ThinkingLogItem {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    (typeof value.session_id === "string" || value.session_id === null) &&
    (typeof value.chat_id === "string" || value.chat_id === null) &&
    typeof value.thinking_log === "string" &&
    Array.isArray(value.reasoning) &&
    value.reasoning.every((step) => typeof step === "string") &&
    typeof value.status_processing === "string" &&
    typeof value.created_at === "string"
  );
}

function isValidThinkingLogListResponse(value: unknown): value is ThinkingLogListResponse {
  return (
    isRecord(value) &&
    typeof value.count === "number" &&
    typeof value.page === "number" &&
    typeof value.page_size === "number" &&
    Array.isArray(value.results) &&
    value.results.every(isValidThinkingLogItem)
  );
}

export async function getThinkingLogsBySession(
  sessionId: string,
  page = 1,
  pageSize = 20,
): Promise<ThinkingLogListResponse> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  const data = await fetchAPI(
    `llm/thinking-logs/${sessionId}/?page=${page}&page_size=${pageSize}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );

  if (!isValidThinkingLogListResponse(data)) {
    throw new Error("The thinking log response is invalid.");
  }

  return data;
}
