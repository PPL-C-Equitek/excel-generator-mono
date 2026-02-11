import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  fetchAPI: vi.fn(),
}));

describe("getMembers", () => {
  it("calls fetchAPI with members endpoint", async () => {
    const { fetchAPI } = await import("@/lib/api");
    const { getMembers } = await import("@/services/members");

    vi.mocked(fetchAPI).mockResolvedValue({
      group: "Kelompok 7",
      members: [{ npm: "2306152172", name: "Siti Shofi Nadhifa" }],
    });

    const result = await getMembers();
    expect(fetchAPI).toHaveBeenCalledWith("members/");
    expect(result.group).toBe("Kelompok 7");
    expect(result.members[0].npm).toBe("2306152172");
  });
});
