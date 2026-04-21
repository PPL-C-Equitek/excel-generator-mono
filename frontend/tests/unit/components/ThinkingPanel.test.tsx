// RED phase: run `npm run test -- tests/unit/components/ThinkingPanel.test.tsx` and confirm it fails until `@/components/ThinkingPanel` is implemented.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ThinkingPanel from "@/components/ThinkingPanel";

describe("ThinkingPanel", () => {
  it("renders streamed thinking content when status is thinking", () => {
    render(<ThinkingPanel status="thinking" content="Menganalisis prompt secara bertahap..." />);

    expect(screen.getByText("Menganalisis prompt secara bertahap...")).toBeInTheDocument();
  });

  it('renders the exact error message "Gagal memuat proses" when status is error', () => {
    render(<ThinkingPanel status="error" content="stream terputus" />);

    expect(screen.getByText("Gagal memuat proses")).toBeInTheDocument();
  });

  it("uses a stable scroll container for long thinking content", () => {
    const { container } = render(
      <ThinkingPanel
        status="thinking"
        content={"baris panjang ".repeat(200)}
      />,
    );

    const panel = container.firstElementChild;

    expect(panel).toHaveClass("max-h-[400px]");
    expect(panel).toHaveClass("overflow-y-auto");
  });
});
