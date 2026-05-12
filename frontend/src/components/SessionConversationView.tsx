import { useEffect, useRef, useState } from "react";
import ThinkingPanel, { THINKING_PANEL_STATUS } from "@/components/ThinkingPanel";
import type { SessionResume, SessionResumeHistoryItem } from "@/services/sessions";
import type { ThinkingLogItem } from "@/services/thinkingLogs";
import {
  downloadSessionOutputCsvFile,
  downloadSessionOutputExcelFile,
  generateJson,
} from "@/services/llm";
import { isJsonObject, type JsonValue } from "@/utils/schemaValidator";

interface SessionConversationViewProps {
  readonly session: SessionResume | null;
  readonly isLoadingSession: boolean;
  readonly sessionError: string | null;
  readonly isSessionNotFound: boolean;
  readonly thinkingLogsByOutputId: Record<string, ThinkingLogItem>;
  readonly isLoadingThinkingLogs: boolean;
  readonly thinkingLogsError: string | null;
}

function toOutputRecord(value: JsonValue): Record<string, unknown> {
  if (isJsonObject(value)) {
    return value;
  }

  return { result: value };
}

function formatSessionDate(value: string | null) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatHistoryTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function getReasoningSteps(
  item: Extract<SessionResumeHistoryItem, { type: "output" }>,
  thinkingLogRecord?: ThinkingLogItem,
): string[] {
  const reasoningSource = thinkingLogRecord?.reasoning ?? item.reasoning;

  if (Array.isArray(reasoningSource)) {
    return reasoningSource.filter((step): step is string => typeof step === "string" && step.trim().length > 0);
  }

  if (isJsonObject(reasoningSource)) {
    const directReasoningSteps = reasoningSource.reasoning_steps;
    if (Array.isArray(directReasoningSteps)) {
      return directReasoningSteps.filter(
        (step): step is string => typeof step === "string" && step.trim().length > 0,
      );
    }

    return Object.values(reasoningSource).filter(
      (value): value is string => typeof value === "string" && value.trim().length > 0,
    );
  }

  return [];
}

function renderReasoningSteps(steps: string[]) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <p className="text-sm font-semibold text-gray-900">Reasoning steps</p>
      <div className="mt-3 space-y-3 text-sm text-gray-700">
        {steps.map((step, index) => (
          <div key={`${step}-${index}`} className="flex items-start gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-700 text-[11px] font-bold text-white">
              {index + 1}
            </span>
            <span className="whitespace-pre-wrap wrap-anywhere leading-6">{step}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function getThinkingPanelContent(
  item: SessionResumeHistoryItem,
  thinkingLogRecord?: ThinkingLogItem,
): string {
  if (thinkingLogRecord?.thinking_log.trim()) {
    return thinkingLogRecord.thinking_log;
  }

  return item.thinking_log;
}

function renderThinkingPanelForOutput(
  item: Extract<SessionResumeHistoryItem, { type: "output" }>,
  thinkingLogRecord: ThinkingLogItem | undefined,
  isLoadingThinkingLogs: boolean,
  thinkingLogsError: string | null,
) {
  const content = getThinkingPanelContent(item, thinkingLogRecord).trim();
  const reasoningSteps = getReasoningSteps(item, thinkingLogRecord);

  if (thinkingLogsError && !content) {
    return <ThinkingPanel status={THINKING_PANEL_STATUS.error} content="" />;
  }

  if (isLoadingThinkingLogs && !content) {
    return (
      <div className="space-y-3">
        {renderReasoningSteps(reasoningSteps)}
        <ThinkingPanel
          status={THINKING_PANEL_STATUS.loading}
          content=""
          animated
        />
      </div>
    );
  }

  return <ThinkingPanel status={THINKING_PANEL_STATUS.success} content={content} />;
}

function SessionHistoryBubble({
  item,
  sessionId,
  thinkingLogRecord,
  isLoadingThinkingLogs,
  thinkingLogsError,
}: {
  readonly item: SessionResumeHistoryItem;
  readonly sessionId: string;
  readonly thinkingLogRecord?: ThinkingLogItem;
  readonly isLoadingThinkingLogs: boolean;
  readonly thinkingLogsError: string | null;
}) {
  if (item.type === "message") {
    const isAssistant = item.role === "assistant";

    return (
      <article
        className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}
      >
        <div
          className={`w-full max-w-[94%] rounded-2xl px-4 py-3 shadow-md ${
            isAssistant
              ? "border border-gray-200 bg-white text-gray-900"
              : "bg-blue-600 text-white"
          }`}
        >
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
            {isAssistant ? "Assistant" : "User"}
          </p>
          <p className="whitespace-pre-wrap wrap-anywhere text-sm leading-6">
            {item.content}
          </p>
          <p className="mt-3 text-[11px] opacity-70">
            {formatHistoryTimestamp(item.created_at)}
          </p>
        </div>
      </article>
    );
  }

  return (
    <article className="flex justify-start">
      <div className="w-full max-w-[96%] space-y-3 rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-md">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
          AI Output
        </p>

        {renderThinkingPanelForOutput(
          item,
          thinkingLogRecord,
          isLoadingThinkingLogs,
          thinkingLogsError,
        )}

        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
          <p className="font-semibold text-gray-900">Your file is ready.</p>
          <p className="mt-1 break-all text-xs text-gray-500">Output ID: {item.id}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                void downloadSessionOutputCsvFile(
                  sessionId,
                  item.id,
                  `session-${sessionId}-output-${item.id}.csv`,
                );
              }}
              className="rounded-xl bg-red-700 px-4 py-2 text-xs font-bold text-white shadow-md transition-all duration-150 hover:bg-red-800 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Download CSV
            </button>
            <button
              type="button"
              onClick={() => {
                void downloadSessionOutputExcelFile(
                  sessionId,
                  item.id,
                  `session-${sessionId}-output-${item.id}.xlsx`,
                );
              }}
              className="rounded-xl border border-red-700 bg-white px-4 py-2 text-xs font-bold text-red-700 shadow-md transition-all duration-150 hover:bg-red-50 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Download Excel
            </button>
          </div>
          <p className="mt-3 text-xs text-gray-500">
            Structured output is available for download as CSV or Excel.
          </p>
        </div>

        <p className="text-[11px] text-gray-500">
          {formatHistoryTimestamp(item.created_at)}
        </p>
      </div>
    </article>
  );
}

export default function SessionConversationView({
  session,
  isLoadingSession,
  sessionError,
  isSessionNotFound,
  thinkingLogsByOutputId,
  isLoadingThinkingLogs,
  thinkingLogsError,
}: Readonly<SessionConversationViewProps>) {
  const [localHistory, setLocalHistory] = useState<SessionResumeHistoryItem[]>([]);
  const [draftMessage, setDraftMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [pendingThinking, setPendingThinking] = useState(false);
  const [pendingReasoningSteps, setPendingReasoningSteps] = useState<string[]>([]);
  const [pendingReasoningVisibleCount, setPendingReasoningVisibleCount] = useState(0);
  const [pendingReasoningPlaybackKey, setPendingReasoningPlaybackKey] = useState<string | null>(null);
  const [pendingReasoningPlaybackCompleteKey, setPendingReasoningPlaybackCompleteKey] =
    useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const pendingGeneratedOutputRef = useRef<SessionResumeHistoryItem | null>(null);

  useEffect(() => {
    if (!session) {
      setLocalHistory([]);
      activeSessionIdRef.current = null;
      return;
    }

    setLocalHistory((previous) => {
      const incomingHistory = session.history;
      const previousSessionId = activeSessionIdRef.current;

      if (previousSessionId !== session.id) {
        activeSessionIdRef.current = session.id;
        return incomingHistory;
      }

      const incomingIds = new Set(incomingHistory.map((item) => `${item.type}-${item.id}`));
      const hasUnsyncedLocalItems = previous.some(
        (item) => !incomingIds.has(`${item.type}-${item.id}`),
      );

      if (hasUnsyncedLocalItems && previous.length >= incomingHistory.length) {
        return previous;
      }

      return incomingHistory;
    });
  }, [session]);

  useEffect(() => {
    if (bottomAnchorRef.current && typeof bottomAnchorRef.current.scrollIntoView === "function") {
      bottomAnchorRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
      return;
    }

    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [localHistory.length]);

  useEffect(() => {
    if (!pendingThinking || pendingReasoningSteps.length === 0 || !pendingReasoningPlaybackKey) {
      return;
    }

    if (pendingReasoningPlaybackCompleteKey === pendingReasoningPlaybackKey) {
      return;
    }

    if (pendingReasoningVisibleCount >= pendingReasoningSteps.length) {
      setPendingReasoningPlaybackCompleteKey(pendingReasoningPlaybackKey);
      return;
    }

    /* v8 ignore next -- @preserve */
    const timer = globalThis.setTimeout(() => {
      setPendingReasoningVisibleCount((current) => current + 1);
    }, pendingReasoningVisibleCount === 0 ? 250 : 700);

    return () => globalThis.clearTimeout(timer);
  }, [
    pendingThinking,
    pendingReasoningSteps.length,
    pendingReasoningPlaybackCompleteKey,
    pendingReasoningPlaybackKey,
    pendingReasoningVisibleCount,
  ]);

  useEffect(() => {
    if (!pendingThinking) {
      return;
    }

    if (
      !pendingReasoningPlaybackKey ||
      pendingReasoningPlaybackCompleteKey !== pendingReasoningPlaybackKey
    ) {
      return;
    }

    const generatedOutput = pendingGeneratedOutputRef.current;
    /* v8 ignore if -- @preserve */
    if (generatedOutput) {
      setLocalHistory((prev) => [...prev, generatedOutput]);
    }

    pendingGeneratedOutputRef.current = null;
    setPendingThinking(false);
    setIsSending(false);
    setPendingReasoningSteps([]);
    setPendingReasoningVisibleCount(0);
    setPendingReasoningPlaybackKey(null);
    setPendingReasoningPlaybackCompleteKey(null);
  }, [pendingReasoningPlaybackCompleteKey, pendingReasoningPlaybackKey, pendingThinking]);

  const userPrompts = localHistory.filter(
    (item) => item.type === "message" && item.role === "user",
  ).length;
  const outputCount = localHistory.filter((item) => item.type === "output").length;
  const firstUserPrompt = localHistory.find(
    (item): item is Extract<SessionResumeHistoryItem, { type: "message" }> =>
      item.type === "message" && item.role === "user" && item.content.trim().length > 0,
  );
  const primaryPrompt = firstUserPrompt?.content ?? session?.title ?? "";
  const latestOutput =
    [...localHistory]
      .reverse()
      .find(
        (item): item is Extract<SessionResumeHistoryItem, { type: "output" }> =>
          item.type === "output",
      ) ?? null;
  const metricCards = [
    {
      label: "Total Events",
      value: localHistory.length,
      tone: "from-gray-900 to-gray-700",
    },
    {
      label: "User Prompts",
      value: userPrompts,
      tone: "from-blue-700 to-blue-500",
    },
    {
      label: "AI Outputs",
      value: outputCount,
      tone: "from-red-700 to-red-600",
    },
  ];
  const canSend = draftMessage.trim().length > 0 && !isSending;

  const renderPendingThinkingBubble = () => {
    if (!pendingThinking) {
      return null;
    }

    const visibleReasoningSteps = pendingReasoningSteps.slice(0, pendingReasoningVisibleCount);

    return (
      <article className="flex justify-start">
        <div className="w-full max-w-[96%] rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-md">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
            AI Thinking
          </p>
          {pendingReasoningSteps.length > 0 ? (
            <div className="space-y-3">
              {renderReasoningSteps(visibleReasoningSteps)}
              <ThinkingPanel
                status={THINKING_PANEL_STATUS.loading}
                content=""
                animated
              />
            </div>
          ) : (
            <ThinkingPanel
              status={THINKING_PANEL_STATUS.loading}
              content=""
              animated
            />
          )}
        </div>
      </article>
    );
  };

  if (isLoadingSession) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-gray-50 px-5 py-5 text-sm text-gray-600">
        Loading session...
      </section>
    );
  }

  if (isSessionNotFound) {
    return (
      <section className="rounded-2xl border border-gray-200 bg-gray-50 px-5 py-5 text-sm text-gray-700">
        Session Not Found
      </section>
    );
  }

  if (sessionError) {
    return (
      <section role="alert" className="rounded-lg border border-red-400 bg-red-50 px-5 py-5 text-sm text-red-700">
        {sessionError}
      </section>
    );
  }

  if (!session) {
    return null;
  }

  const handleSendMessage = async () => {
    const trimmedMessage = draftMessage.trim();
    /* v8 ignore if -- @preserve */
    if (!trimmedMessage) {
      return;
    }

    /* v8 ignore if -- @preserve */
    if (isSending) {
      return;
    }

    if (!latestOutput) {
      setSendError("No output is available yet to continue this chat context.");
      return;
    }

    const optimisticUserMessage: SessionResumeHistoryItem = {
      type: "message",
      id: `temp-user-${Date.now()}`,
      role: "user",
      content: trimmedMessage,
      thinking_log: "",
      target_output_id: latestOutput.id,
      created_at: new Date().toISOString(),
    };

    setDraftMessage("");
    setSendError(null);
    setIsSending(true);
    setPendingThinking(true);
    setPendingReasoningSteps([]);
    setPendingReasoningVisibleCount(0);
    setPendingReasoningPlaybackKey(null);
    setPendingReasoningPlaybackCompleteKey(null);
    pendingGeneratedOutputRef.current = null;
    setLocalHistory((prev) => [...prev, optimisticUserMessage]);

    try {
      const followUpPayload = {
        previous_output: latestOutput.output_json,
        user_prompt: trimmedMessage,
      };

      const llmResult = await generateJson(
        followUpPayload,
        undefined,
        undefined,
        { sessionId: session.id },
      );

      const generatedOutput: SessionResumeHistoryItem = {
        type: "output",
        id: llmResult.output_id ?? `temp-output-${Date.now()}`,
        chat_id: llmResult.chat_id ?? null,
        parent_output_id: latestOutput.id,
        output_json: toOutputRecord(llmResult.output_json),
        thinking_log: llmResult.reasoning?.thinking_log?.trim() ?? "",
        reasoning: {
          reasoning_steps: llmResult.reasoning?.reasoning_steps ?? [],
          final_answer: llmResult.reasoning?.final_answer ?? "",
        },
        created_at: new Date().toISOString(),
      };

      pendingGeneratedOutputRef.current = generatedOutput;
      setPendingReasoningSteps(
        llmResult.reasoning?.reasoning_steps?.filter(
          (step): step is string => typeof step === "string" && step.trim().length > 0,
        ) ?? [],
      );
      setPendingReasoningVisibleCount(0);
      setPendingReasoningPlaybackKey(generatedOutput.id);
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to send follow-up message.";
      setSendError(errorMessage);
      setDraftMessage(trimmedMessage);
      setLocalHistory((prev) => prev.filter((item) => item.id !== optimisticUserMessage.id));
      pendingGeneratedOutputRef.current = null;
      setPendingReasoningSteps([]);
      setPendingReasoningVisibleCount(0);
      setPendingReasoningPlaybackKey(null);
      setPendingReasoningPlaybackCompleteKey(null);
      setPendingThinking(false);
      setIsSending(false);
    } finally {
      if (!pendingGeneratedOutputRef.current) {
        setPendingThinking(false);
        setIsSending(false);
      }
    }
  };

  return (
    <section
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl"
      aria-labelledby="session-conversation-title"
    >
      <header className="space-y-2 border-b border-gray-200 px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
          Session View
        </p>
        <h2 id="session-conversation-title" className="text-lg font-bold text-gray-900">
          {session.title}
        </h2>
        <p className="text-xs text-gray-500">{session.id}</p>
        {thinkingLogsError ? (
          <div role="alert" className="rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700">
            {thinkingLogsError}
          </div>
        ) : null}
      </header>

      <section className="border-b border-gray-200 bg-gray-50 px-5 py-3">
        <details>
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-widest text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
            Session Info
          </summary>
          <div className="mt-3 space-y-3">
            <p className="whitespace-pre-wrap wrap-anywhere text-sm leading-6 text-gray-800">
              {primaryPrompt}
            </p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <article className="rounded-xl bg-white px-3 py-2 ring-1 ring-gray-200">
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-500">Created</p>
                <p className="mt-1 text-xs font-semibold text-gray-800">{formatSessionDate(session.created_at)}</p>
              </article>
              <article className="rounded-xl bg-white px-3 py-2 ring-1 ring-gray-200">
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-500">Updated</p>
                <p className="mt-1 text-xs font-semibold text-gray-800">{formatSessionDate(session.updated_at)}</p>
              </article>
              {metricCards.map((metric) => (
                <article
                  key={metric.label}
                  className={`rounded-xl bg-linear-to-br ${metric.tone} px-3 py-2 text-white shadow-md`}
                >
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/85">
                    {metric.label}
                  </p>
                  <p className="mt-1 text-lg font-bold leading-none">{metric.value}</p>
                </article>
              ))}
            </div>
          </div>
        </details>
      </section>

      <div ref={scrollContainerRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
        <div className="space-y-4">
          {localHistory.map((item) => (
            <SessionHistoryBubble
              key={`${item.type}-${item.id}`}
              item={item}
              sessionId={session.id}
              thinkingLogRecord={
                item.type === "output"
                  ? thinkingLogsByOutputId[item.chat_id ?? item.id]
                  : undefined
              }
              isLoadingThinkingLogs={isLoadingThinkingLogs}
              thinkingLogsError={thinkingLogsError}
            />
          ))}
          {renderPendingThinkingBubble()}
          <div ref={bottomAnchorRef} />
        </div>
      </div>

      <section className="border-t border-gray-200 bg-gray-50 px-5 py-3">
        <label htmlFor="history-followup-input" className="sr-only">
          Follow-up message
        </label>
        <div className="flex items-end gap-3">
          <textarea
            id="history-followup-input"
            aria-label="Follow-up message"
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            rows={2}
            placeholder="Continue this session conversation..."
            disabled={isSending}
            className="min-h-12 flex-1 resize-none rounded-xl border border-gray-300 bg-gray-100 px-4 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="button"
            onClick={() => {
              void handleSendMessage();
            }}
            disabled={!canSend}
            className="h-11 shrink-0 rounded-xl bg-red-700 px-5 text-sm font-bold text-white shadow-md transition-all duration-150 hover:bg-red-800 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>
        {sendError ? (
          <div role="alert" className="mt-3 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700">
            {sendError}
          </div>
        ) : null}
      </section>
    </section>
  );
}
