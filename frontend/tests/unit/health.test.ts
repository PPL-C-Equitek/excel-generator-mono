import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  fetchAPI: vi.fn(),
}));

describe("getHealth", () => {
  it("calls fetchAPI with health endpoint", async () => {
    const { fetchAPI } = await import("@/lib/api");
    const { getHealth } = await import("@/services/health");

    vi.mocked(fetchAPI).mockResolvedValue({ status: "ok" });
    const result = await getHealth();

    expect(fetchAPI).toHaveBeenCalledWith("health/");
    expect(result).toEqual({ status: "ok" });
  });
});
