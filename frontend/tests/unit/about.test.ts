import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  fetchAPI: vi.fn(),
}));

describe("getAbout", () => {
  it("calls fetchAPI with about endpoint", async () => {
    const { fetchAPI } = await import("@/lib/api");
    const { getAbout } = await import("@/services/about");

    vi.mocked(fetchAPI).mockResolvedValue({
      team: "PPL C - Equitek",
      project: "Excel Generator",
    });

    const result = await getAbout();
    expect(fetchAPI).toHaveBeenCalledWith("about/");
    expect(result.team).toBe("PPL C - Equitek");
    expect(result.project).toBe("Excel Generator");
  });
});
