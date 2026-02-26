/**
 * [RED] — Tests for <LLMClient /> component
 *
 * Uses vi.mock to isolate the component from the real service.
 * All tests will FAIL until src/components/LLMClient.tsx is implemented.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import LLMClient from "@/components/LLMClient";
import { generateJson } from "@/services/llm";

vi.mock("@/services/llm", () => ({
    generateJson: vi.fn(),
}));

afterEach(() => {
    cleanup();
    vi.clearAllMocks();
});

const VALID_INPUT = JSON.stringify({ key: "value" });

/**
 * Helper: set textarea value directly via fireEvent.change.
 * userEvent.type in v14 interprets `{` as a keyboard modifier tag,
 * which breaks JSON strings — fireEvent.change avoids that entirely.
 */
function fillTextarea(value: string) {
    fireEvent.change(screen.getByRole("textbox"), { target: { value } });
}

describe("LLMClient — Positive", () => {
    it("menampilkan hasil output_json di UI setelah submit berhasil", async () => {
        vi.mocked(generateJson).mockResolvedValue({
            output_json: { summary: "Extracted", rows: [{ id: 1 }] },
        });

        render(<LLMClient />);
        fillTextarea(VALID_INPUT);
        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        expect(await screen.findByText(/Extracted/i)).toBeInTheDocument();
    });

    it("menampilkan state loading selagi menunggu respons", async () => {
        // Promise yang tidak pernah resolve → loading tetap tampil
        vi.mocked(generateJson).mockReturnValue(new Promise(() => { }));

        render(<LLMClient />);
        fillTextarea(VALID_INPUT);
        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
});

describe("LLMClient — Negative (Error Messages)", () => {
    it("menampilkan pesan error saat API Key invalid (401)", async () => {
        vi.mocked(generateJson).mockRejectedValue(new Error("API Key tidak valid"));

        render(<LLMClient />);
        fillTextarea(VALID_INPUT);
        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        expect(await screen.findByText("API Key tidak valid")).toBeInTheDocument();
    });

    it("menampilkan pesan error saat quota habis (429)", async () => {
        vi.mocked(generateJson).mockRejectedValue(
            new Error("Quota LLM habis, coba lagi nanti")
        );

        render(<LLMClient />);
        fillTextarea(VALID_INPUT);
        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        expect(
            await screen.findByText("Quota LLM habis, coba lagi nanti")
        ).toBeInTheDocument();
    });

    it("menampilkan pesan error saat timeout (504)", async () => {
        vi.mocked(generateJson).mockRejectedValue(
            new Error("Request timeout, coba lagi")
        );

        render(<LLMClient />);
        fillTextarea(VALID_INPUT);
        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        expect(
            await screen.findByText("Request timeout, coba lagi")
        ).toBeInTheDocument();
    });
});

describe("LLMClient — Edge Cases", () => {
    it("menampilkan validasi error saat input kosong (submit tanpa mengisi)", async () => {
        render(<LLMClient />);

        await userEvent.click(screen.getByRole("button", { name: /generate/i }));

        await waitFor(() => {
            expect(
                screen.getByText("Input tidak boleh kosong")
            ).toBeInTheDocument();
        });
        expect(generateJson).not.toHaveBeenCalled();
    });
});
