import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HistorySidebarList from "@/components/HistorySidebarList";
import { getSessionResume } from "@/services/sessions";

vi.mock("@/services/sessions", () => ({
  getSessionResume: vi.fn(),
}));

const mockGetSessionResume = vi.mocked(getSessionResume);

function invokeBeforeInputViaReactProps(target: HTMLElement, data: string | null) {
  const reactPropsKey = Object.keys(target).find((key) => key.startsWith("__reactProps$"));
  if (!reactPropsKey) {
    throw new Error("React props key was not found on target element.");
  }

  const reactProps = (target as unknown as Record<string, unknown>)[reactPropsKey] as {
    onBeforeInput?: (event: {
      nativeEvent: { data: string | null };
      currentTarget: HTMLInputElement;
      preventDefault: () => void;
    }) => void;
  };
  const preventDefault = vi.fn();

  reactProps.onBeforeInput?.({
    nativeEvent: { data },
    currentTarget: target as HTMLInputElement,
    preventDefault,
  });

  return preventDefault;
}

function setNullSelectionRange(input: HTMLInputElement) {
  const originalSelectionStart = Object.getOwnPropertyDescriptor(input, "selectionStart");
  const originalSelectionEnd = Object.getOwnPropertyDescriptor(input, "selectionEnd");

  Object.defineProperty(input, "selectionStart", {
    configurable: true,
    get: () => null,
  });
  Object.defineProperty(input, "selectionEnd", {
    configurable: true,
    get: () => null,
  });

  return () => {
    if (originalSelectionStart) {
      Object.defineProperty(input, "selectionStart", originalSelectionStart);
    }
    if (originalSelectionEnd) {
      Object.defineProperty(input, "selectionEnd", originalSelectionEnd);
    }
  };
}

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

function makeListState(
  overrides?: Partial<{
    items: typeof historyItems;
    isLoading: boolean;
    loadError: string | null;
    renamingHistoryId: string | null;
    deletingHistoryId: string | null;
    reloadHistory: () => Promise<void>;
    renameHistory: (historyId: string, customName: string) => Promise<boolean>;
    deleteHistory: (historyId: string) => Promise<boolean>;
  }>
) {
  return {
    items: historyItems,
    isLoading: false,
    renamingHistoryId: null,
    deletingHistoryId: null,
    loadError: null,
    reloadHistory: vi.fn().mockResolvedValue(undefined),
    renameHistory: vi.fn().mockResolvedValue(true),
    deleteHistory: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
}

describe("HistorySidebarList", () => {
  let listState: ReturnType<typeof makeListState>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSessionResume.mockResolvedValue({
      id: "session-1",
      title: "Session",
      created_at: "2026-04-10T10:00:00Z",
      updated_at: "2026-04-10T10:00:00Z",
      last_message_at: null,
      last_output_at: null,
      history: [],
    });
    listState = makeListState();
  });

  it("renders search input and grouped history items", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />);

    expect(screen.getByText("History List")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search history" })).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
  });

  it("shows one-line truncated title style for long history names", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />);

    const longNameLink = screen.getByTitle(historyItems[0].original_name);
    const titleElement = within(longNameLink).getByText(historyItems[0].original_name);

    expect(titleElement).toHaveClass("truncate");
  });

  it("filters history items by search query", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search history" }), {
      target: { value: "budget" },
    });

    expect(screen.getByText("Budget Sheet")).toBeInTheDocument();
    expect(screen.queryByText(historyItems[0].original_name)).not.toBeInTheDocument();
  });

  it("links history items with session ids to the session-aware history route", () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({
          items: [
            {
              ...historyItems[1],
              session_id: "11111111-1111-1111-1111-111111111111",
            },
          ],
        })}
      />
    );

    const link = screen.getByRole("link", { name: historyItems[1].custom_name });

    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining(`historyId=${historyItems[1].id}`)
    );
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("sessionId=11111111-1111-1111-1111-111111111111")
    );
  });

  it("does not prefetch resume when a history item has no session id", () => {
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />);

    fireEvent.click(screen.getByRole("link", { name: historyItems[0].original_name }));

    expect(mockGetSessionResume).not.toHaveBeenCalled();
  });

  it("prefetches resume when a history item has session id", async () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[1].id}
        {...makeListState({
          items: [{ ...historyItems[1], session_id: "session-prefetch-1" }],
        })}
      />
    );

    fireEvent.click(screen.getByRole("link", { name: historyItems[1].custom_name }));

    await waitFor(() => {
      expect(mockGetSessionResume).toHaveBeenCalledWith("session-prefetch-1");
    });
  });

  it("swallows resume prefetch errors from history item click", async () => {
    mockGetSessionResume.mockRejectedValueOnce(new Error("prefetch failed"));
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[1].id}
        {...makeListState({
          items: [{ ...historyItems[1], session_id: "session-prefetch-error" }],
        })}
      />
    );

    fireEvent.click(screen.getByRole("link", { name: historyItems[1].custom_name }));

    await waitFor(() => {
      expect(mockGetSessionResume).toHaveBeenCalledWith("session-prefetch-error");
    });
  });

  it("shows loading, load error, empty and no matches states", async () => {
    const reloadHistory = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ isLoading: true })}
      />
    );
    expect(screen.getByText("Loading history...")).toBeInTheDocument();

    rerender(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({
          loadError: "Failed to load history.",
          reloadHistory,
        })}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(reloadHistory).toHaveBeenCalledTimes(1);
    });

    rerender(
      <HistorySidebarList selectedHistoryId={null} {...makeListState({ items: [] })} />
    );
    expect(screen.getByText("No history yet")).toBeInTheDocument();

    rerender(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...makeListState()} />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search history" }), {
      target: { value: "not-found-keyword" },
    });
    expect(screen.getByText("No matches.")).toBeInTheDocument();
  });

  it("renders Last 7 days, Last 30 days and Older groups", () => {
    render(
      <HistorySidebarList
        selectedHistoryId={null}
        {...makeListState({
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
        })}
      />
    );

    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
    expect(screen.getByText("Older")).toBeInTheDocument();
  });

  it("places invalid created_at into Older group", () => {
    render(
      <HistorySidebarList
        selectedHistoryId={null}
        {...makeListState({
          items: [
          {
            ...historyItems[0],
            id: "77777777-7777-7777-7777-777777777777",
            created_at: "invalid-date",
          },
        ],
        })}
      />
    );

    expect(screen.getByText("Older")).toBeInTheDocument();
    expect(screen.getByText(historyItems[0].original_name)).toBeInTheDocument();
  });

  it("opens rename popup from action menu and submits rename", async () => {
    const renameHistory = vi.fn().mockResolvedValue(true);
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renameHistory })}
      />
    );

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
    render(<HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />);

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
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renameHistory })}
      />
    );

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

  it("does not submit rename when title is empty and shows validation message", async () => {
    const renameHistory = vi.fn().mockResolvedValue(true);
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renameHistory })}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    fireEvent.change(screen.getByLabelText("File Name"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(renameHistory).not.toHaveBeenCalled();
      expect(screen.getByText("Title cannot be empty.")).toBeInTheDocument();
    });
  });

  it("shows max length validation when user attempts to paste more than 120 characters", async () => {
    const renameHistory = vi.fn().mockResolvedValue(true);
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renameHistory })}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name");
    fireEvent.paste(renameInput, {
      clipboardData: {
        getData: () => "A".repeat(121),
      },
    });

    expect(screen.getByText("Max 120 Character")).toBeInTheDocument();
    expect(renameHistory).not.toHaveBeenCalled();
  });

  it("ignores empty beforeinput and empty paste payload without triggering max-length error", () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name");
    const preventDefault = invokeBeforeInputViaReactProps(renameInput as HTMLInputElement, null);
    fireEvent.paste(renameInput, {
      clipboardData: {
        getData: () => "",
      },
    });

    expect(preventDefault).not.toHaveBeenCalled();
    expect(screen.queryByText("Max 120 Character")).not.toBeInTheDocument();
  });

  it("blocks beforeinput when the next length would exceed 120 characters", async () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name");
    fireEvent.change(renameInput, {
      target: { value: "A".repeat(120) },
    });

    let preventDefault!: ReturnType<typeof vi.fn>;
    await act(async () => {
      preventDefault = invokeBeforeInputViaReactProps(renameInput as HTMLInputElement, "B");
    });

    expect(preventDefault).toHaveBeenCalledTimes(1);
  });

  it("uses value-length fallback for beforeinput when selection range is unavailable", async () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name") as HTMLInputElement;
    fireEvent.change(renameInput, {
      target: { value: "A".repeat(120) },
    });

    const restoreSelectionRange = setNullSelectionRange(renameInput);
    let preventDefault!: ReturnType<typeof vi.fn>;
    await act(async () => {
      preventDefault = invokeBeforeInputViaReactProps(renameInput, "B");
    });
    restoreSelectionRange();

    expect(preventDefault).toHaveBeenCalledTimes(1);
  });

  it("uses value-length fallback for paste when selection range is unavailable", () => {
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState()}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name") as HTMLInputElement;
    fireEvent.change(renameInput, {
      target: { value: "A".repeat(120) },
    });

    const restoreSelectionRange = setNullSelectionRange(renameInput);
    fireEvent.paste(renameInput, {
      clipboardData: {
        getData: () => "B",
      },
    });
    restoreSelectionRange();

    expect(screen.getByText("Max 120 Character")).toBeInTheDocument();
  });

  it("keeps max-length validation on over-limit submit and clears it on next input change", async () => {
    const renameHistory = vi.fn().mockResolvedValue(true);
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renameHistory })}
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    const renameInput = screen.getByLabelText("File Name");
    fireEvent.change(renameInput, {
      target: { value: "A".repeat(121) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText("Max 120 Character")).toBeInTheDocument();
    });
    expect(renameHistory).not.toHaveBeenCalled();

    fireEvent.change(renameInput, {
      target: { value: "Valid Title" },
    });
    expect(screen.queryByText("Max 120 Character")).not.toBeInTheDocument();
  });

  it("shows rename dialog pending state when rename is in progress", () => {
    const { rerender } = render(
      <HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));

    rerender(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ renamingHistoryId: historyItems[0].id })}
      />
    );

    expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled();
  });

  it("opens delete popup from action menu and confirms deletion", async () => {
    const deleteHistory = vi.fn().mockResolvedValue(true);
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ deleteHistory })}
      />
    );

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
    render(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ deleteHistory })}
      />
    );

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
    const { rerender } = render(
      <HistorySidebarList selectedHistoryId={historyItems[0].id} {...listState} />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: `Actions for ${historyItems[0].original_name}`,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    rerender(
      <HistorySidebarList
        selectedHistoryId={historyItems[0].id}
        {...makeListState({ deletingHistoryId: historyItems[0].id })}
      />
    );

    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
  });
});
