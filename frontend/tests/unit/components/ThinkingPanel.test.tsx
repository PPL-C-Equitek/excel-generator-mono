import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ThinkingPanel from "@/components/ThinkingPanel";
import { thinkingPanelInternals } from "@/components/ThinkingPanel";

type ThinkingPanelContractProps = {
  status?: "idle" | "loading" | "thinking" | "success" | "error";
  content?: string | null;
  animated?: boolean;
};

function renderThinkingPanel(props: ThinkingPanelContractProps = {}) {
  const mergedProps = {
    status: "success",
    content: "Analisis selesai.",
    animated: false,
    ...props,
  };

  return render(<ThinkingPanel {...(mergedProps as never)} />);
}

describe("ThinkingPanel", () => {
  it("renders markdown content inside the thinking panel body", () => {
    renderThinkingPanel({
      status: "success",
      content: "**Analisis**\n\n- Langkah pertama\n- Langkah kedua",
    });

    const panel = screen.getByLabelText("Proses berpikir");
    const body = within(panel).getByTestId("thinking-panel-content");
    const strongText = body.querySelector("strong");
    const bulletItems = within(body).getAllByRole("listitem");

    expect(panel).toBeInTheDocument();
    expect(strongText).toHaveTextContent("Analisis");
    expect(bulletItems).toHaveLength(2);
    expect(bulletItems[0]).toHaveTextContent("Langkah pertama");
    expect(bulletItems[1]).toHaveTextContent("Langkah kedua");
  });

  it("preserves plain text line breaks when the log is not markdown", () => {
    renderThinkingPanel({
      status: "success",
      content: "Baris pertama\nBaris kedua",
    });

    const body = screen.getByTestId("thinking-panel-content");

    expect(body).toHaveTextContent("Baris pertama");
    expect(body).toHaveTextContent("Baris kedua");
    expect(body).toHaveClass("whitespace-pre-wrap");
  });

  it("keeps long content inside a max-height scroll region to prevent layout shift", () => {
    renderThinkingPanel({
      status: "success",
      content: "baris panjang ".repeat(500),
    });

    const scrollRegion = screen.getByTestId("thinking-panel-scroll-region");

    expect(scrollRegion).toHaveClass("max-h-[400px]");
    expect(scrollRegion).toHaveClass("overflow-y-auto");
  });

  it('shows "Gagal memuat proses" when the log stream or fetch fails', () => {
    renderThinkingPanel({
      status: "error",
      content: "partial streamed content",
    });

    const alert = screen.getByRole("alert", { name: "Proses berpikir" });

    expect(alert).toHaveTextContent("Gagal memuat proses");
    expect(alert).not.toHaveTextContent("partial streamed content");
  });

  it("shows an animated loading state while waiting for the LLM response", () => {
    renderThinkingPanel({
      status: "loading",
      content: "",
      animated: true,
    });

    const panel = screen.getByLabelText("Proses berpikir");

    expect(panel).toHaveTextContent("Memuat proses berpikir...");
    expect(panel).toHaveAttribute("role", "status");
    expect(panel).toHaveClass("animate-pulse");
  });

  it("shows an empty state when no thinking log exists for the selected chat history", () => {
    renderThinkingPanel({
      status: "success",
      content: "   ",
      animated: false,
    });

    const panel = screen.getByLabelText("Proses berpikir");

    expect(panel).toHaveTextContent("Belum ada proses yang tersedia.");
    expect(panel).not.toHaveClass("animate-pulse");
  });

  it("treats null content as empty state safely", () => {
    renderThinkingPanel({
      status: "success",
      content: null,
    });

    expect(screen.getByText("Belum ada proses yang tersedia.")).toBeInTheDocument();
  });

  it("renders raw content fallback for thinking status with null content", () => {
    renderThinkingPanel({
      status: "thinking",
      content: null,
      animated: true,
    });

    const panel = screen.getByLabelText("Proses berpikir");
    expect(panel).toHaveAttribute("aria-busy", "true");
    expect(panel).toHaveTextContent("Memuat proses berpikir...");
  });

  it("renders mixed inline markdown safely, including empty and unclosed markers", () => {
    renderThinkingPanel({
      status: "success",
      content: "Awalan **tebal** akhiran **** sisa **tidak tertutup",
    });

    const body = screen.getByTestId("thinking-panel-content");
    const strongTexts = body.querySelectorAll("strong");

    expect(strongTexts).toHaveLength(2);
    expect(strongTexts[0]).toHaveTextContent("tebal");
    expect(strongTexts[1]).toHaveTextContent("sisa");
    expect(body).toHaveTextContent("Awalan");
    expect(body).toHaveTextContent("akhiran ** sisa tidak tertutup");
  });

  it("treats malformed list markers as plain text instead of list content", () => {
    renderThinkingPanel({
      status: "success",
      content: "-   ",
    });

    const body = screen.getByTestId("thinking-panel-content");

    expect(within(body).queryByRole("list")).not.toBeInTheDocument();
    expect(body).toHaveTextContent("-");
  });

  it("keeps unclosed inline markdown markers as literal text", () => {
    render(
      <div data-testid="inline-markdown">
        {thinkingPanelInternals.renderInlineMarkdown("Awal **tidak tertutup")}
      </div>,
    );

    expect(screen.getByTestId("inline-markdown")).toHaveTextContent(
      "Awal **tidak tertutup",
    );
  });

  it("returns false for empty and empty-bold markdown detection cases", () => {
    expect(thinkingPanelInternals.hasBoldMarkdown("")).toBe(false);
    expect(thinkingPanelInternals.hasBoldMarkdown("****")).toBe(false);
    expect(thinkingPanelInternals.looksLikeMarkdown("****")).toBe(false);
  });

  it('uses the "empty" fallback when creating keys from blank content', () => {
    const keyCounts = new Map<string, number>();

    expect(
      thinkingPanelInternals.createContentKey("paragraph", "   \n\t   ", keyCounts),
    ).toBe("paragraph-empty-1");
  });
});
