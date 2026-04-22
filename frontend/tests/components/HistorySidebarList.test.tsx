import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HistorySidebarList from "@/components/HistorySidebarList";
import { useHistoryFiles } from "@/hooks/useHistoryFiles";

vi.mock("@/hooks/useHistoryFiles", () => ({
  useHistoryFiles: vi.fn(),
}));

const mockUseHistoryFiles = vi.mocked(useHistoryFiles);

const historyItems = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    original_name: "bahasa-indonesia-file-yang-sangat-panjang-sekali.pdf",
    custom_name: "",
    status_processing: "completed",
    created_at: "2026-04-22T03:00:00Z",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    original_name: "budget-2026.xlsx",
    custom_name: "Budget Sheet",
    status_processing: "completed",
    created_at: "2026-04-21T03:00:00Z",
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
});
