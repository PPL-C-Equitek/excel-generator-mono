import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import { getAbout } from "@/services/about";
import { getHealth } from "@/services/health";
import { getMembers } from "@/services/members";

vi.mock("@/services/health", () => ({
    getHealth: vi.fn(),
}));

vi.mock("@/services/about", () => ({
    getAbout: vi.fn(),
}));

vi.mock("@/services/members", () => ({
    getMembers: vi.fn(),
}));

describe("Home page", () => {
    it("renders fetched data", async () => {
        vi.mocked(getHealth).mockResolvedValue({ status: "ok", message: "Backend is running!" });
        vi.mocked(getAbout).mockResolvedValue({ team: "PPL C - Equitek", project: "Excel Generator" });
        vi.mocked(getMembers).mockResolvedValue({
            group: "Kelompok 7",
            members: [
                { npm: "2306152172", name: "Siti Shofi Nadhifa" },
                { npm: "2306152260", name: "Steven Setiawan" },
            ],
        });

        render(<Home />);

        expect(await screen.findByText("OK: Backend is running!")).toBeInTheDocument();
        expect(await screen.findByText("Team: PPL C - Equitek")).toBeInTheDocument();
        expect(await screen.findByText("Project: Excel Generator")).toBeInTheDocument();
        expect(await screen.findByText("2306152172 - Siti Shofi Nadhifa")).toBeInTheDocument();
        expect(await screen.findByText("2306152260 - Steven Setiawan")).toBeInTheDocument();
    });

    it("shows error when fetch fails", async () => {
        vi.mocked(getHealth).mockRejectedValue(new Error("boom"));
        vi.mocked(getAbout).mockResolvedValue({ team: "PPL C - Equitek", project: "Excel Generator" });
        vi.mocked(getMembers).mockResolvedValue({ group: "Kelompok 7", members: [] });

        render(<Home />);

        expect(await screen.findByText("Error: boom")).toBeInTheDocument();
    });
});
