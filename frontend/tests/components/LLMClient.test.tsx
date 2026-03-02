import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import LLMClient from "@/components/LLMClient";
import { generateJson } from "@/services/llm";

vi.mock("react-syntax-highlighter", () => ({
  Prism: ({ children }: { children: string }) => <pre data-testid="syntax-hl">{children}</pre>,
}));
vi.mock("react-syntax-highlighter/dist/esm/styles/prism", () => ({
  atomDark: {},
}));

vi.mock("@/services/llm", () => ({
  generateJson: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const VALID_INPUT = JSON.stringify({ key: "value" });

function fillTextarea(value: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value } });
}

describe("LLMClient", () => {
  it("shows empty state on first render", () => {
    render(<LLMClient />);
    expect(screen.getByText("Hasil akan tampil di sini")).toBeInTheDocument();
  });

  it("renders output_json on successful submit", async () => {
    vi.mocked(generateJson).mockResolvedValue({
      output_json: { summary: "Extracted", rows: [{ id: 1 }] },
    });

    render(<LLMClient />);
    fillTextarea(VALID_INPUT);
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    expect(await screen.findByText(/Extracted/i)).toBeInTheDocument();
  });

  it("shows loading state while waiting for response", async () => {
    vi.mocked(generateJson).mockReturnValue(new Promise(() => {}));

    render(<LLMClient />);
    fillTextarea(VALID_INPUT);
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    expect(screen.getByRole("button", { name: /generating/i })).toBeDisabled();
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("shows known error message from service", async () => {
    vi.mocked(generateJson).mockRejectedValue(new Error("API Key tidak valid"));

    render(<LLMClient />);
    fillTextarea(VALID_INPUT);
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    expect(await screen.findByText("API Key tidak valid")).toBeInTheDocument();
  });

  it("validates empty input and does not call service", async () => {
    render(<LLMClient />);

    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText("Input tidak boleh kosong")).toBeInTheDocument();
    });
    expect(generateJson).not.toHaveBeenCalled();
  });

  it("validates invalid JSON and does not call service", async () => {
    render(<LLMClient />);
    fillTextarea("ini bukan json { tidak valid");
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText("Input harus berupa JSON yang valid")).toBeInTheDocument();
    });
    expect(generateJson).not.toHaveBeenCalled();
  });

  it("shows fallback message when service rejects non-Error", async () => {
    vi.mocked(generateJson).mockRejectedValue("unexpected");

    render(<LLMClient />);
    fillTextarea(VALID_INPUT);
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));

    expect(await screen.findByText("Terjadi kesalahan tidak diketahui")).toBeInTheDocument();
  });
});
