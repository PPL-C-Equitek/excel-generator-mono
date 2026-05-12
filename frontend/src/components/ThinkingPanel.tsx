"use client";

import { useId, useRef, type ReactNode } from "react";
import { useAutoScrollToBottom } from "@/hooks/useAutoScrollToBottom";

export const THINKING_PANEL_STATUS = {
  idle: "idle",
  loading: "loading",
  thinking: "thinking",
  success: "success",
  error: "error",
} as const;

export type ThinkingPanelStatus =
  (typeof THINKING_PANEL_STATUS)[keyof typeof THINKING_PANEL_STATUS];

export interface ThinkingPanelProps {
  status: ThinkingPanelStatus;
  content: string | null;
  animated?: boolean;
}

const panelLabel = "Thinking process";
const shellClassName =
  "rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 shadow-md";
const scrollRegionClassName =
  "max-h-[400px] overflow-y-auto pr-2 [scrollbar-width:thin] [scrollbar-color:#d1d5db_transparent] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-track]:bg-transparent";
const statusClassName =
  "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-md";
const contentClassName = "space-y-3 whitespace-pre-wrap leading-6 text-gray-700";

function createContentKey(
  prefix: string,
  value: string,
  keyCounts: Map<string, number>,
): string {
  const normalizedValue = value.replaceAll(/\s+/g, " ").trim() || "empty";
  const baseKey = `${prefix}-${normalizedValue.slice(0, 60)}`;
  const nextCount = (keyCounts.get(baseKey) ?? 0) + 1;
  keyCounts.set(baseKey, nextCount);
  return `${baseKey}-${nextCount}`;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    const boldStart = text.indexOf("**", cursor);
    if (boldStart === -1) {
      nodes.push(
        <span key={`text-${cursor}`}>{text.slice(cursor)}</span>,
      );
      break;
    }

    if (boldStart > cursor) {
      nodes.push(
        <span key={`text-${cursor}`}>{text.slice(cursor, boldStart)}</span>,
      );
    }

    const boldEnd = text.indexOf("**", boldStart + 2);
    if (boldEnd === -1) {
      nodes.push(
        <span key={`text-${boldStart}`}>{text.slice(boldStart)}</span>,
      );
      break;
    }

    const boldContent = text.slice(boldStart + 2, boldEnd);
    if (boldContent.length > 0) {
      nodes.push(
        <strong key={`strong-${boldStart}`}>{boldContent}</strong>,
      );
      cursor = boldEnd + 2;
      continue;
    }

    nodes.push(<span key={`text-${boldStart}`}>**</span>);
    cursor = boldStart + 2;
  }

  return nodes;
}

function looksLikeMarkdown(content: string): boolean {
  const lines = content.split("\n");
  const hasListSyntax = lines.some((line) => getListItemContent(line) !== null);

  return hasListSyntax || hasBoldMarkdown(content);
}

function hasBoldMarkdown(content: string): boolean {
  let searchFrom = 0;

  while (searchFrom < content.length) {
    const boldStart = content.indexOf("**", searchFrom);
    if (boldStart === -1) {
      return false;
    }

    const boldEnd = content.indexOf("**", boldStart + 2);
    if (boldEnd > boldStart + 2) {
      return true;
    }

    searchFrom = boldStart + 2;
  }

  return false;
}

function getListItemContent(line: string): string | null {
  const trimmedStart = line.trimStart();
  if (
    trimmedStart.length < 3 ||
    (!trimmedStart.startsWith("-") && !trimmedStart.startsWith("*"))
  ) {
    return null;
  }

  let contentStart = 1;
  while (
    contentStart < trimmedStart.length &&
    trimmedStart[contentStart] === " "
  ) {
    contentStart += 1;
  }

  if (contentStart === 1 || contentStart >= trimmedStart.length) {
    return null;
  }

  return trimmedStart.slice(contentStart);
}

function renderMarkdownContent(content: string) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let listItems: string[] = [];
  let paragraphLines: string[] = [];
  const blockKeyCounts = new Map<string, number>();

  const flushParagraph = () => {
    if (paragraphLines.length === 0) {
      return;
    }

    const paragraph = paragraphLines.join("\n");
    blocks.push(
      <p
        key={createContentKey("paragraph", paragraph, blockKeyCounts)}
        className="whitespace-pre-wrap"
      >
        {renderInlineMarkdown(paragraph)}
      </p>,
    );
    paragraphLines = [];
  };

  const flushList = () => {
    if (listItems.length === 0) {
      return;
    }

    const listKey = createContentKey("list", listItems.join("|"), blockKeyCounts);
    const itemKeyCounts = new Map<string, number>();

    blocks.push(
      <ul
        key={listKey}
        className="list-disc space-y-1 pl-5 text-gray-700"
      >
        {listItems.map((item) => (
          <li key={createContentKey("item", item, itemKeyCounts)}>
            {renderInlineMarkdown(item)}
          </li>
        ))}
      </ul>,
    );
    listItems = [];
  };

  for (const line of lines) {
    const listMatch = getListItemContent(line);

    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch);
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraphLines.push(line);
  }

  flushParagraph();
  flushList();

  return blocks;
}

function renderSafeContent(content: string) {
  if (!looksLikeMarkdown(content)) {
    return <p className="whitespace-pre-wrap">{content}</p>;
  }

  return renderMarkdownContent(content);
}

export const thinkingPanelInternals = {
  createContentKey,
  renderInlineMarkdown,
  hasBoldMarkdown,
  getListItemContent,
  looksLikeMarkdown,
};

export default function ThinkingPanel({
  status,
  content,
  animated = false,
}: Readonly<ThinkingPanelProps>) {
  const titleId = useId();
  const scrollRegionRef = useRef<HTMLDivElement>(null);
  const normalizedContent = content?.trim() ?? "";
  const showEmptyState =
    status !== THINKING_PANEL_STATUS.error &&
    status !== THINKING_PANEL_STATUS.loading &&
    status !== THINKING_PANEL_STATUS.thinking &&
    normalizedContent.length === 0;
  const showLoadingState =
    status === THINKING_PANEL_STATUS.loading ||
    status === THINKING_PANEL_STATUS.thinking;
  const isStreaming =
    status === THINKING_PANEL_STATUS.loading ||
    status === THINKING_PANEL_STATUS.thinking;
  let bodyContent: ReactNode;

  useAutoScrollToBottom(scrollRegionRef, isStreaming, content ?? "");

  if (showLoadingState) {
    bodyContent = (
      <p
        data-testid="thinking-panel-content"
        className="whitespace-pre-wrap text-gray-500"
      >
        Loading thinking process...
      </p>
    );
  } else if (showEmptyState) {
    bodyContent = (
      <p
        data-testid="thinking-panel-content"
        className="whitespace-pre-wrap text-gray-500"
      >
        No process is available yet.
      </p>
    );
  } else {
    bodyContent = (
      <div
        data-testid="thinking-panel-content"
        className={contentClassName}
      >
        {renderSafeContent(normalizedContent)}
      </div>
    );
  }

  if (status === THINKING_PANEL_STATUS.error) {
    return (
      <section
        role="alert"
        aria-label={panelLabel}
        aria-labelledby={titleId}
        className={`${statusClassName} border-red-400 bg-red-50 text-red-700`}
      >
        <h3 id={titleId} className="sr-only">
          {panelLabel}
        </h3>
        <span aria-hidden className="mt-0.5 text-red-500">
          !
        </span>
        <p>Failed to load process</p>
      </section>
    );
  }

  return (
    <section
      aria-label={panelLabel}
      aria-labelledby={titleId}
      aria-busy={isStreaming}
      className={`${shellClassName} ${animated ? "animate-pulse" : ""}`}
    >
      <header className="mb-2">
        <h3 id={titleId} className="sr-only">
          {panelLabel}
        </h3>
      </header>
      <div
        ref={scrollRegionRef}
        data-testid="thinking-panel-scroll-region"
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-relevant="additions text"
        className={scrollRegionClassName}
      >
        {bodyContent}
      </div>
    </section>
  );
}
