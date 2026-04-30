import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ThinkingPanel, {
  THINKING_PANEL_STATUS,
} from "@/components/ThinkingPanel";

describe("ThinkingPanel", () => {
  it("renders streamed thinking content when status is thinking", () => {
    render(
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.thinking}
        content="Menganalisis prompt secara bertahap..."
      />,
    );

    const content = screen.getByText("Menganalisis prompt secara bertahap...");
    const panel = content.parentElement;

    expect(content).toBeInTheDocument();
    expect(panel).toHaveAttribute("role", "status");
    expect(panel).toHaveAttribute("aria-live", "polite");
    expect(panel).toHaveAttribute("aria-label", "Proses berpikir");
  });

  it('renders the exact error message "Gagal memuat proses" when status is error', () => {
    render(
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.error}
        content="stream terputus"
      />,
    );

    const errorMessage = screen.getByText("Gagal memuat proses");
    const panel = errorMessage.parentElement;

    expect(errorMessage).toBeInTheDocument();
    expect(panel).toHaveAttribute("role", "alert");
    expect(panel).toHaveAttribute("aria-label", "Proses berpikir");
    expect(panel).not.toHaveAttribute("aria-live");
    expect(panel).toHaveClass("border-red-200");
    expect(errorMessage).not.toHaveAttribute("role");
  });

  it("preserves multiline content formatting for streamed thinking output", () => {
    render(
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.success}
        content={"line1\nline2"}
      />,
    );

    const content = screen.getByText((_, element) => {
      return (
        element?.tagName === "P" && element.textContent === "line1\nline2"
      );
    });

    expect(content).toBeInTheDocument();
    expect(content).toHaveClass("whitespace-pre-wrap");
    expect(content.textContent).toBe("line1\nline2");
  });

  it("uses a stable scroll container for long thinking content", () => {
    const { container } = render(
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.thinking}
        content={"baris panjang ".repeat(200)}
      />,
    );

    const panel = container.firstElementChild;

    expect(panel).toHaveClass("max-h-[400px]");
    expect(panel).toHaveClass("overflow-y-auto");
  });
});
