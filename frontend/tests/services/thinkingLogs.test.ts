import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import * as auth from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  getValidAccessToken: vi.fn(),
}));

const mockGetValidAccessToken = vi.mocked(auth.getValidAccessToken);

describe("thinking logs service", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns thinking logs for an authenticated session", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    const fetchSpy = vi.spyOn(api, "fetchAPI").mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      results: [
        {
          id: "output-1",
          session_id: "session-1",
          chat_id: null,
          thinking_log: "Langkah 1",
          reasoning: ["step1", "step2"],
          status_processing: "completed",
          created_at: "2026-04-10T10:01:00Z",
        },
      ],
    });

    const thinkingLogsService = await import("@/services/thinkingLogs");
    const result = await thinkingLogsService.getThinkingLogsBySession("session-1");

    expect(fetchSpy).toHaveBeenCalledWith(
      "llm/thinking-logs/session-1/?page=1&page_size=20",
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer access-token",
        },
      }
    );
    expect(result.results).toHaveLength(1);
    expect(result.results[0].id).toBe("output-1");
  });

  it("accepts thinking log items with string session_id and chat_id", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      results: [
        {
          id: "output-2",
          session_id: "session-2",
          chat_id: "chat-2",
          thinking_log: "Langkah valid",
          reasoning: ["step"],
          status_processing: "completed",
          created_at: "2026-04-10T10:01:00Z",
        },
      ],
    });

    const thinkingLogsService = await import("@/services/thinkingLogs");
    const result = await thinkingLogsService.getThinkingLogsBySession("session-2");

    expect(result.results[0].session_id).toBe("session-2");
    expect(result.results[0].chat_id).toBe("chat-2");
  });

  it("throws an authentication error when no access token is available", async () => {
    mockGetValidAccessToken.mockResolvedValue(null);
    const fetchSpy = vi.spyOn(api, "fetchAPI");

    const thinkingLogsService = await import("@/services/thinkingLogs");

    await expect(thinkingLogsService.getThinkingLogsBySession("session-1")).rejects.toThrow(
      "Authentication credentials were not provided."
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws when the thinking log payload is invalid", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      results: [
        {
          id: "output-1",
          session_id: "session-1",
          chat_id: null,
          thinking_log: "Langkah 1",
          reasoning: [1],
          status_processing: "completed",
          created_at: "2026-04-10T10:01:00Z",
        },
      ],
    });

    const thinkingLogsService = await import("@/services/thinkingLogs");

    await expect(thinkingLogsService.getThinkingLogsBySession("session-1")).rejects.toThrow(
      "The thinking log response is invalid."
    );
  });

  it("throws when a thinking log item is not an object", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      results: [null],
    });

    const thinkingLogsService = await import("@/services/thinkingLogs");

    await expect(thinkingLogsService.getThinkingLogsBySession("session-1")).rejects.toThrow(
      "The thinking log response is invalid."
    );
  });

  it("throws when session_id has invalid type", async () => {
    mockGetValidAccessToken.mockResolvedValue("access-token");
    vi.spyOn(api, "fetchAPI").mockResolvedValue({
      count: 1,
      page: 1,
      page_size: 20,
      results: [
        {
          id: "output-3",
          session_id: 123,
          chat_id: null,
          thinking_log: "Langkah 1",
          reasoning: ["step"],
          status_processing: "completed",
          created_at: "2026-04-10T10:01:00Z",
        },
      ],
    });

    const thinkingLogsService = await import("@/services/thinkingLogs");

    await expect(thinkingLogsService.getThinkingLogsBySession("session-1")).rejects.toThrow(
      "The thinking log response is invalid."
    );
  });
});