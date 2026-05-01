import { fetchAPI } from "@/lib/api";
import { getValidAccessToken } from "@/lib/auth";

export interface SessionResumeHistoryMessage {
  type: "message";
  id: string;
  role: string;
  content: string;
  thinking_log: string;
  target_output_id?: string | null;
  created_at: string;
}

export interface SessionResumeHistoryOutput {
  type: "output";
  id: string;
  chat_id?: string | null;
  parent_output_id?: string | null;
  output_json: Record<string, unknown>;
  thinking_log: string;
  reasoning: Record<string, unknown>;
  created_at: string;
}

export type SessionResumeHistoryItem =
  | SessionResumeHistoryMessage
  | SessionResumeHistoryOutput;

export interface SessionResume {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  last_output_at: string | null;
  history: SessionResumeHistoryItem[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isValidHistoryMessage(value: unknown): value is SessionResumeHistoryMessage {
  return (
    isRecord(value) &&
    value.type === "message" &&
    typeof value.id === "string" &&
    typeof value.role === "string" &&
    typeof value.content === "string" &&
    typeof value.thinking_log === "string" &&
    typeof value.created_at === "string"
  );
}

function isValidHistoryOutput(value: unknown): value is SessionResumeHistoryOutput {
  return (
    isRecord(value) &&
    value.type === "output" &&
    typeof value.id === "string" &&
    isRecord(value.output_json) &&
    typeof value.thinking_log === "string" &&
    isRecord(value.reasoning) &&
    typeof value.created_at === "string"
  );
}

function isValidSessionResume(value: unknown): value is SessionResume {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string" &&
    (typeof value.last_message_at === "string" || value.last_message_at === null) &&
    (typeof value.last_output_at === "string" || value.last_output_at === null) &&
    Array.isArray(value.history) &&
    value.history.every((item) => isValidHistoryMessage(item) || isValidHistoryOutput(item))
  );
}

export async function getSessionResume(sessionId: string): Promise<SessionResume> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    throw new Error("Authentication credentials were not provided.");
  }

  const data = await fetchAPI(`sessions/${sessionId}/resume/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!isValidSessionResume(data)) {
    throw new Error("The session resume response is invalid.");
  }

  return data;
}
