import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HistorySidebarList from "@/components/HistorySidebarList";
import { useHistoryFiles } from "@/hooks/useHistoryFiles";

vi.mock("@/hooks/useHistoryFiles", () => ({
  useHistoryFiles: vi.fn(),
}));

const mockUseHistoryFiles = vi.mocked(useHistoryFiles);

function isoDaysAgo(daysAgo: number) {
  const now = new Date();
  const date = new Date(now);
  date.setUTCDate(now.getUTCDate() - daysAgo);
  return date.toISOString();
}

const historyItems = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    original_name: "bahasa-indonesia-file-yang-sangat-panjang-sekali.pdf",
    custom_name: "",
    status_processing: "completed",
    created_at: isoDaysAgo(0),
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    original_name: "budget-2026.xlsx",
    custom_name: "Budget Sheet",
    status_processing: "completed",
    created_at: isoDaysAgo(1),
  },
];

function makeHookState(overrides?: Partial<ReturnType<typeof useHistoryFiles>>) {
  return {
    items: historyItems,
    count: 2,
    limit: 50,
    offset: 0,
    isLoading: false,
    renamingHistoryId: null,
    deletingHistoryId: null,
    isDownloading: vi.fn().mockReturnValue(false),
    downloadError: null,
    loadError: null,
    mutationError: null,
    error: null,
    reloadHistory: vi.fn().mockResolvedValue(undefined),
    goToNextPage: vi.fn().mockResolvedValue(undefined),
    goToPreviousPage: vi.fn().mockResolvedValue(undefined),
    downloadCsv: vi.fn().mockResolvedValue(undefined),
    downloadExcel: vi.fn().mockResolvedValue(undefined),
    renameHistory: vi.fn().mockResolvedValue(true),
    deleteHistory: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
}

describe("HistorySidebarList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseHistoryFiles.mockReturnValue(makeHookState());
  });

  it("renders search input and grouped history items", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    expect(screen.getByText("History List")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search history" })).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
  });

  it("shows one-line truncated title style for long history names", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    const longNameLink = screen.getByTitle(historyItems[0].original_name);
    const titleElement = within(longNameLink).getByText(historyItems[0].original_name);

    expect(titleElement).toHaveClass("truncate");
  });

  it("filters history items by search query", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search history" }), {
      target: { value: "budget" },
    });

    expect(screen.getByText("Budget Sheet")).toBeInTheDocument();
    expect(screen.queryByText(historyItems[0].original_name)).not.toBeInTheDocument();
  });

  it("shows loading, load error, empty and no matches states", async () => {
    const reloadHistory = vi.fn().mockResolvedValue(undefined);

    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        isLoading: true,
      })
    );
    const { rerender } = render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);
    expect(screen.getByText("Loading history...")).toBeInTheDocument();

    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        loadError: "Failed to load history.",
        reloadHistory,
      })
    );
    rerender(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(reloadHistory).toHaveBeenCalledTimes(1);
    });

    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        items: [],
        count: 0,
      })
    );
    rerender(<HistorySidebarList selectedHistoryId={null} />);
    expect(screen.getByText("No history yet.")).toBeInTheDocument();

    mockUseHistoryFiles.mockReturnValue(makeHookState());
    rerender(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search history" }), {
      target: { value: "not-found-keyword" },
    });
    expect(screen.getByText("No matches.")).toBeInTheDocument();
  });

  it("renders Last 7 days, Last 30 days and Older groups", () => {
    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        items: [
          {
            ...historyItems[0],
            id: "33333333-3333-3333-3333-333333333333",
            created_at: isoDaysAgo(3),
          },
          {
            ...historyItems[0],
            id: "66666666-6666-6666-6666-666666666666",
            created_at: isoDaysAgo(5),
          },
          {
            ...historyItems[0],
            id: "44444444-4444-4444-4444-444444444444",
            created_at: isoDaysAgo(20),
          },
          {
            ...historyItems[0],
            id: "55555555-5555-5555-5555-555555555555",
            created_at: isoDaysAgo(40),
          },
        ],
        count: 4,
      })
    );

    render(<HistorySidebarList selectedHistoryId={null} />);

    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
    expect(screen.getByText("Older")).toBeInTheDocument();
  });

  it("places invalid created_at into Older group", () => {
    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        items: [
          {
            ...historyItems[0],
            id: "77777777-7777-7777-7777-777777777777",
            created_at: "invalid-date",
          },
        ],
        count: 1,
      })
    );

    render(<HistorySidebarList selectedHistoryId={null} />);

    expect(screen.getByText("Older")).toBeInTheDocument();
    expect(screen.getByText(historyItems[0].original_name)).toBeInTheDocument();
  });

  it("opens rename popup from action menu and submits rename", async () => {
    const renameHistory = vi.fn().mockResolvedValue(true);
    mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }));

    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    fireEvent.change(screen.getByLabelText("File Name"), {
      target: { value: "Laporan Baru" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(renameHistory).toHaveBeenCalledWith(historyItems[0].id, "Laporan Baru");
    });
  });

  it("toggles action menu closed when actions button clicked twice", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    const actionButton = screen.getByRole("button", {
      name: `Actions for ${historyItems[0].original_name}`,
    });

    fireEvent.click(actionButton);
    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();

    fireEvent.click(actionButton);
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  });

  it("keeps rename dialog open when rename fails and closes on cancel", async () => {
    const renameHistory = vi.fn().mockResolvedValue(false);
    mockUseHistoryFiles.mockReturnValue(makeHookState({ renameHistory }));

    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(renameHistory).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows rename dialog pending state when rename is in progress", () => {
    const { rerender } = render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        renamingHistoryId: historyItems[0].id,
      })
    );
    rerender(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
  });

  it("opens delete popup from action menu and confirms deletion", async () => {
    const deleteHistory = vi.fn().mockResolvedValue(true);
    mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }));

    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: /^Delete$/ }));

    await waitFor(() => {
      expect(deleteHistory).toHaveBeenCalledWith(historyItems[0].id);
    });
  });

  it("keeps delete dialog open when delete fails and closes on cancel", async () => {
    const deleteHistory = vi.fn().mockResolvedValue(false);
    mockUseHistoryFiles.mockReturnValue(makeHookState({ deleteHistory }));

    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: /^Delete$/ }));

    await waitFor(() => {
      expect(deleteHistory).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows delete dialog pending state when delete is in progress", () => {
    const { rerender } = render(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    mockUseHistoryFiles.mockReturnValue(
      makeHookState({
        deletingHistoryId: historyItems[0].id,
      })
    );
    rerender(<HistorySidebarList selectedHistoryId={historyItems[0].id} />);

    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
  });
});
