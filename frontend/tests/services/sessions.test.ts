import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import * as auth from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  getValidAccessToken: vi.fn(),
}));

const mockGetValidAccessToken = vi.mocked(auth.getValidAccessToken);

describe("sessions service", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns a session resume payload for an authenticated user", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      id: "session-1",
      title: "Resume Session",
      created_at: "2026-04-10T10:00:00Z",
      updated_at: "2026-04-10T10:01:00Z",
      last_message_at: "2026-04-10T10:00:30Z",
      last_output_at: null,
      history: [
        {
          type: "message",
          id: "message-1",
          role: "user",
          content: "Tolong lanjutkan.",
          thinking_log: "",
          target_output_id: null,
          created_at: "2026-04-10T10:00:00Z",
        },
        {
          type: "output",
          id: "output-1",
          chat_id: null,
          parent_output_id: null,
          output_json: { summary: { total_rows: 1 } },
          thinking_log: "Langkah 1",
          reasoning: { step1: "Normalisasi" },
          created_at: "2026-04-10T10:01:00Z",
        },
      ],
    });

    const sessionsService = await import("@/services/sessions");
    const result = await sessionsService.getSessionResume("session-1");

    expect(fetchSpy).toHaveBeenCalledWith("sessions/session-1/resume/", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer access-token",
      },
    });
    expect(result.id).toBe("session-1");
    expect(result.history).toHaveLength(2);
  });

  it("throws an authentication error when no access token is available", async () => {
    mockGetValidAccessToken.mockResolvedValue(null);
    const fetchSpy = vi.spyOn(api, "fetchAPI");

    const sessionsService = await import("@/services/sessions");

    await expect(sessionsService.getSessionResume("session-1")).rejects.toThrow(
      "Authentication credentials were not provided."
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws when the session resume payload is invalid", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue({
      id: "session-1",
      title: "Resume Session",
      created_at: "2026-04-10T10:00:00Z",
      updated_at: "2026-04-10T10:01:00Z",
      last_message_at: 123,
      last_output_at: null,
      history: [
        {
          type: "message",
          id: "message-1",
          role: "user",
          content: "Tolong lanjutkan.",
          thinking_log: "",
          target_output_id: null,
          created_at: "2026-04-10T10:00:00Z",
        },
      ],
    });

    const sessionsService = await import("@/services/sessions");

    await expect(sessionsService.getSessionResume("session-1")).rejects.toThrow(
      "The session resume response is invalid."
    );
  });

  it("appends a session message when authenticated", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      ok: true,
      session_id: "session-1",
      chat_id: "chat-1",
    });

    const sessionsService = await import("@/services/sessions");
    const result = await sessionsService.appendSessionMessage(
      "session-1",
      "Lanjutkan analisis"
    );

    expect(fetchSpy).toHaveBeenCalledWith("sessions/session-1/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer access-token",
      },
      body: JSON.stringify({ message: "Lanjutkan analisis" }),
    });
    expect(result).toEqual({
      ok: true,
      session_id: "session-1",
      chat_id: "chat-1",
    });
  });

  it("throws auth error when append message is requested without token", async () => {
    mockGetValidAccessToken.mockResolvedValue(null);
    const fetchSpy = vi.spyOn(api, "fetchAPI");

    const sessionsService = await import("@/services/sessions");
    await expect(
      sessionsService.appendSessionMessage("session-1", "Lanjutkan")
    ).rejects.toThrow("Authentication credentials were not provided.");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws when append message returns a non-object payload", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue("invalid-response");

    const sessionsService = await import("@/services/sessions");
    await expect(
      sessionsService.appendSessionMessage("session-1", "Lanjutkan")
    ).rejects.toThrow("The session chat response is invalid.");
  });
});
