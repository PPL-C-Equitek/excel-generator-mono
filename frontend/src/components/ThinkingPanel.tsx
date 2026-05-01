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

const panelLabel = "Proses berpikir";
const shellClassName =
  "rounded-2xl border border-slate-200/80 bg-slate-50/95 px-4 py-3 text-sm text-slate-700 shadow-sm";
const scrollRegionClassName =
  "max-h-[400px] overflow-y-auto pr-2 [scrollbar-width:thin] [scrollbar-color:#cbd5e1_transparent] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-track]:bg-transparent";
const statusClassName =
  "flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-sm";
const contentClassName = "space-y-3 whitespace-pre-wrap leading-6 text-slate-700";

function renderInlineMarkdown(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={`strong-${index}`}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}

function looksLikeMarkdown(content: string): boolean {
  return /^\s*[-*]\s+/m.test(content) || /\*\*[^*]+\*\*/.test(content);
}

function renderMarkdownContent(content: string) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let listItems: string[] = [];
  let paragraphLines: string[] = [];

  const flushParagraph = () => {
    if (paragraphLines.length === 0) {
      return;
    }

    const paragraph = paragraphLines.join("\n");
    blocks.push(
      <p key={`paragraph-${blocks.length}`} className="whitespace-pre-wrap">
        {renderInlineMarkdown(paragraph)}
      </p>,
    );
    paragraphLines = [];
  };

  const flushList = () => {
    if (listItems.length === 0) {
      return;
    }

    blocks.push(
      <ul
        key={`list-${blocks.length}`}
        className="list-disc space-y-1 pl-5 text-slate-700"
      >
        {listItems.map((item, index) => (
          <li key={`item-${index}`}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>,
    );
    listItems = [];
  };

  for (const line of lines) {
    const listMatch = line.match(/^\s*[-*]\s+(.+)$/);

    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
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

  useAutoScrollToBottom(scrollRegionRef, isStreaming, content ?? "");

  if (status === THINKING_PANEL_STATUS.error) {
    return (
      <section
        role="alert"
        aria-label={panelLabel}
        aria-labelledby={titleId}
        className={`${statusClassName} border-red-200 bg-red-50 text-red-700`}
      >
        <h3 id={titleId} className="sr-only">
          {panelLabel}
        </h3>
        <span aria-hidden className="mt-0.5 text-red-500">
          !
        </span>
        <p>Gagal memuat proses</p>
      </section>
    );
  }

  return (
    <section
      role="status"
      aria-live="polite"
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
        {showLoadingState ? (
          <p
            data-testid="thinking-panel-content"
            className="whitespace-pre-wrap text-slate-500"
          >
            Memuat proses berpikir...
          </p>
        ) : showEmptyState ? (
          <p
            data-testid="thinking-panel-content"
            className="whitespace-pre-wrap text-slate-500"
          >
            Belum ada proses yang tersedia.
          </p>
        ) : (
          <div
            data-testid="thinking-panel-content"
            className={contentClassName}
          >
            {renderSafeContent(normalizedContent)}
          </div>
        )}
      </div>
    </section>
  );
}
