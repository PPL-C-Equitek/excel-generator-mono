import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import ReasoningProcessPanel, {
  DEFAULT_LOADING_TEXT,
  ReasoningStepsDropdown,
} from "@/components/ReasoningProcessPanel";

describe("ReasoningProcessPanel", () => {
  it("renders reasoning steps with the default loading text", () => {
    render(
      <ReasoningProcessPanel
        steps={["Inspect the uploaded file.", "Map columns to schema."]}
      />,
    );

    expect(screen.getByTestId("reasoning-steps")).toBeInTheDocument();
    expect(screen.getByText("Inspect the uploaded file.")).toBeInTheDocument();
    expect(screen.getByText("Map columns to schema.")).toBeInTheDocument();
    expect(screen.getByText(DEFAULT_LOADING_TEXT)).toBeInTheDocument();
  });

  it("renders a custom loading text", () => {
    render(<ReasoningProcessPanel loadingText="Preparing reasoning output..." />);

    expect(screen.getByText("Preparing reasoning output...")).toBeInTheDocument();
  });

  it("hides the loading indicator when showLoading is false", () => {
    render(
      <ReasoningProcessPanel
        steps={["Reasoning is already complete."]}
        showLoading={false}
      />,
    );

    expect(screen.getByText("Reasoning is already complete.")).toBeInTheDocument();
    expect(screen.queryByText(DEFAULT_LOADING_TEXT)).not.toBeInTheDocument();
  });
});

describe("ReasoningStepsDropdown", () => {
  it("renders nothing when there are no non-empty reasoning steps", () => {
    const { container } = render(<ReasoningStepsDropdown steps={["", "   "]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("keeps reasoning steps collapsed until the user opens the dropdown", async () => {
    const user = userEvent.setup();

    render(
      <ReasoningStepsDropdown
        steps={[" First step with whitespace ", "Second step"]}
      />,
    );

    const toggle = screen.getByRole("button", { name: /reasoning steps/i });

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("reasoning-steps-dropdown")).toBeInTheDocument();
    expect(screen.queryByText("First step with whitespace")).not.toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("First step with whitespace")).toBeInTheDocument();
    expect(screen.getByText("Second step")).toBeInTheDocument();
  });
});
