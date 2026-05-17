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

function isTemporaryOutputId(value: string): boolean {
  return value.startsWith("temp-output-");
}

function AssistantAvatar() {
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-700 text-xs font-extrabold tracking-widest text-white shadow-md">
      AI
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-md">
      U
    </div>
  );
}

function SendIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3.5 10L16.5 3.5L13 16.5L9.75 10.75L3.5 10Z" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function FileIcon({ className = "h-10 w-10" }: Readonly<{ className?: string }>) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="8" y="4" width="28" height="36" rx="3" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" />
      <path d="M28 4L36 12H28V4Z" fill="var(--brand-secondary-primary)" stroke="var(--brand-primary)" strokeWidth="1.5" strokeLinejoin="round" />
      <rect x="13" y="20" width="18" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
      <rect x="13" y="25" width="13" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
      <rect x="13" y="30" width="15" height="2" rx="1" fill="var(--brand-primary)" opacity="0.5" />
    </svg>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getStringRecordValue(
  record: Record<string, unknown> | null | undefined,
  keys: readonly string[],
): string | null {
  if (!record) {
    return null;
  }

  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

function getNumberRecordValue(
  record: Record<string, unknown> | null | undefined,
  keys: readonly string[],
): number | null {
  if (!record) {
    return null;
  }

  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
      return value;
    }
  }

  return null;
}

function getDocumentInfo(output?: Extract<SessionResumeHistoryItem, { type: "output" }> | null) {
  const documentInfo = output?.output_json.document_info;
  return isJsonObject(documentInfo) ? documentInfo : null;
}

function extractUploadedFileName(content: string): string | null {
  const normalizedContent = content.trim();
  const uploadPrefix = "uploaded file:";
  if (!normalizedContent.toLowerCase().startsWith(uploadPrefix)) {
    return null;
  }

  const fileName = normalizedContent.slice(uploadPrefix.length).trim();
  return fileName ? fileName : null;
}

function isUploadBootstrapMessage(item: Extract<SessionResumeHistoryItem, { type: "message" }>) {
  const normalizedContent = item.content.trim().toLowerCase();
  return (
    item.role === "user" &&
    (
      normalizedContent === "uploaded file" ||
      normalizedContent === "uploaded file for conversion" ||
      normalizedContent.startsWith("uploaded file:")
    )
  );
}

function getPairedOutputForMessage(
  history: SessionResumeHistoryItem[],
  message: Extract<SessionResumeHistoryItem, { type: "message" }>,
  messageIndex: number,
): Extract<SessionResumeHistoryItem, { type: "output" }> | null {
  const outputForMessage = history.find(
    (candidate): candidate is Extract<SessionResumeHistoryItem, { type: "output" }> =>
      candidate.type === "output" && candidate.chat_id === message.id,
  );

  if (outputForMessage) {
    return outputForMessage;
  }

  return (
    history
      .slice(messageIndex + 1)
      .find(
        (candidate): candidate is Extract<SessionResumeHistoryItem, { type: "output" }> =>
          candidate.type === "output",
      ) ?? null
  );
}

function getUploadPreview(
  sessionId: string,
  message: Extract<SessionResumeHistoryItem, { type: "message" }>,
  output?: Extract<SessionResumeHistoryItem, { type: "output" }> | null,
) {
  const documentInfo = getDocumentInfo(output);
  const fileName =
    extractUploadedFileName(message.content) ??
    getStringRecordValue(documentInfo, ["filename", "file_name", "original_name", "original_filename"]) ??
    (output ? `session-${sessionId}-output-${output.id}.xlsx` : "Uploaded file");
  const fileSizeBytes =
    getNumberRecordValue(output?.output_json, ["size_bytes", "file_size_bytes", "file_size"]) ??
    getNumberRecordValue(documentInfo, ["size_bytes", "file_size_bytes", "file_size"]);
  const schemaName = getStringRecordValue(output?.output_json, ["schema_name", "custom_schema_name"]);

  return { fileName, fileSizeBytes, schemaName };
}

function HistoryAttachedFileCard({
  fileName,
  fileSizeBytes,
}: Readonly<{ fileName: string; fileSizeBytes: number | null }>) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-white/15 p-3 text-left ring-1 ring-white/20">
      <FileIcon className="h-10 w-10 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="break-all text-sm font-semibold leading-snug text-white">
          {fileName}
        </p>
        {fileSizeBytes !== null ? (
          <p className="mt-1 text-xs text-blue-100">{formatFileSize(fileSizeBytes)}</p>
        ) : null}
      </div>
    </div>
  );
}

function InitialUploadBubble({
  item,
  sessionId,
  pairedOutput,
}: Readonly<{
  item: Extract<SessionResumeHistoryItem, { type: "message" }>;
  sessionId: string;
  pairedOutput?: Extract<SessionResumeHistoryItem, { type: "output" }> | null;
}>) {
  const { fileName, fileSizeBytes, schemaName } = getUploadPreview(sessionId, item, pairedOutput);

  return (
    <article className="flex w-full items-start justify-end gap-3">
      <div className="max-w-xl rounded-2xl rounded-tr-sm bg-blue-600 p-4 text-sm text-white shadow-md lg:max-w-2xl">
        <p className="font-semibold">Generate this file.</p>
        {schemaName ? (
          <div className="mt-3 rounded-xl bg-white/15 px-3 py-2 text-left ring-1 ring-white/20">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-100">
              Schema context
            </p>
            <p className="mt-1 break-words text-sm font-semibold text-white">
              {schemaName}
            </p>
          </div>
        ) : null}
        <div className="mt-3">
          <HistoryAttachedFileCard fileName={fileName} fileSizeBytes={fileSizeBytes} />
        </div>
        <p className="mt-3 text-[11px] text-blue-100">
          {formatHistoryTimestamp(item.created_at)}
        </p>
      </div>
      <UserAvatar />
    </article>
  );
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
    <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-900">Reasoning steps</p>
      <div className="mt-3 space-y-3 text-sm text-slate-700">
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
  pairedOutput,
  thinkingLogRecord,
  isLoadingThinkingLogs,
  thinkingLogsError,
}: {
  readonly item: SessionResumeHistoryItem;
  readonly sessionId: string;
  readonly pairedOutput?: Extract<SessionResumeHistoryItem, { type: "output" }> | null;
  readonly thinkingLogRecord?: ThinkingLogItem;
  readonly isLoadingThinkingLogs: boolean;
  readonly thinkingLogsError: string | null;
}) {
  if (item.type === "message") {
    const isAssistant = item.role === "assistant";

    if (isAssistant) {
      return (
        <article className="flex w-full items-start justify-start gap-3">
          <AssistantAvatar />
          <div className="max-w-2xl rounded-2xl rounded-tl-sm bg-white p-4 text-sm text-gray-700 shadow-sm ring-1 ring-gray-200 lg:max-w-3xl">
            <span className="sr-only">Assistant</span>
            <p className="whitespace-pre-wrap wrap-anywhere leading-6">{item.content}</p>
            <p className="mt-3 text-[11px] text-gray-400">
              {formatHistoryTimestamp(item.created_at)}
            </p>
          </div>
        </article>
      );
    }

    if (isUploadBootstrapMessage(item)) {
      return (
        <InitialUploadBubble
          item={item}
          sessionId={sessionId}
          pairedOutput={pairedOutput}
        />
      );
    }

    return (
      <article className="flex w-full items-start justify-end gap-3">
        <div className="max-w-xl rounded-2xl rounded-tr-sm bg-blue-600 p-4 text-sm text-white shadow-md lg:max-w-2xl">
          <p className="whitespace-pre-wrap wrap-anywhere leading-6">{item.content}</p>
          <p className="mt-3 text-[11px] text-blue-100">
            {formatHistoryTimestamp(item.created_at)}
          </p>
        </div>
        <UserAvatar />
      </article>
    );
  }

  return (
    <article className="flex w-full items-start justify-start gap-3">
      <AssistantAvatar />
      <div className="max-w-2xl space-y-4 rounded-2xl rounded-tl-sm bg-white p-4 text-sm text-gray-700 shadow-sm ring-1 ring-gray-200 lg:max-w-3xl">
        <span className="sr-only">AI Output</span>
        {renderThinkingPanelForOutput(
          item,
          thinkingLogRecord,
          isLoadingThinkingLogs,
          thinkingLogsError,
        )}

        <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
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
              className="rounded-lg bg-red-700 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="rounded-lg border border-red-700 bg-white px-4 py-2 text-xs font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Download Excel
            </button>
          </div>
          <p className="mt-3 text-xs text-gray-500">
            Structured output is available for download as CSV or Excel.
          </p>
        </div>

        <p className="text-[11px] text-gray-400">
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

  const latestOutput =
    [...localHistory]
      .reverse()
      .find(
        (item): item is Extract<SessionResumeHistoryItem, { type: "output" }> =>
          item.type === "output",
      ) ?? null;
  const canSend = draftMessage.trim().length > 0 && !isSending;

  const renderPendingThinkingBubble = () => {
    if (!pendingThinking) {
      return null;
    }

    const visibleReasoningSteps = pendingReasoningSteps.slice(0, pendingReasoningVisibleCount);

    return (
      <article className="flex w-full items-start justify-start gap-3">
        <AssistantAvatar />
        <div className="max-w-2xl rounded-2xl rounded-tl-sm bg-white p-4 text-sm text-gray-700 shadow-sm ring-1 ring-gray-200 lg:max-w-3xl">
          <span className="sr-only">AI Thinking</span>
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
      <section className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-5 text-sm text-slate-600">
        Loading session...
      </section>
    );
  }

  if (isSessionNotFound) {
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-5 text-sm text-amber-800">
        Session Not Found
      </section>
    );
  }

  if (sessionError) {
    return (
      <section className="rounded-2xl border border-red-200 bg-red-50 px-5 py-5 text-sm text-red-700">
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
      const useTargetOutputId = !isTemporaryOutputId(latestOutput.id);
      const followUpPayload = useTargetOutputId
        ? {
            user_prompt: trimmedMessage,
          }
        : {
            previous_output: latestOutput.output_json,
            user_prompt: trimmedMessage,
          };

      const llmResult = await generateJson(
        followUpPayload,
        undefined,
        undefined,
        {
          sessionId: session.id,
          targetOutputId: useTargetOutputId ? latestOutput.id : undefined,
        },
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
      className="flex h-full min-h-0 flex-col overflow-hidden bg-gray-50"
      aria-labelledby="session-conversation-title"
    >
      <h2 id="session-conversation-title" className="sr-only">
        {session.title}
      </h2>

      <div ref={scrollContainerRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
        {thinkingLogsError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
            {thinkingLogsError}
          </div>
        ) : null}
        <div className="space-y-5">
          {localHistory.map((item, index) => (
            <SessionHistoryBubble
              key={`${item.type}-${item.id}`}
              item={item}
              sessionId={session.id}
              pairedOutput={
                item.type === "message"
                  ? getPairedOutputForMessage(localHistory, item, index)
                  : null
              }
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

      <section className="border-t border-gray-200 px-4 py-4 sm:px-6 lg:px-8">
        <label htmlFor="history-followup-input" className="sr-only">
          Follow-up message
        </label>
        <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-end">
          <textarea
            id="history-followup-input"
            aria-label="Follow-up message"
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            rows={2}
            placeholder="Ask a follow-up question or refine the output..."
            disabled={isSending}
            className="min-h-12 flex-1 resize-none rounded-2xl border border-gray-300 bg-gray-100 px-4 py-3 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="button"
            onClick={() => {
              void handleSendMessage();
            }}
            disabled={!canSend}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-red-700 px-5 py-3 text-sm font-bold text-white shadow-md transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSending ? "Sending..." : "Send"}
            <SendIcon />
          </button>
        </div>
        {sendError ? <p className="mt-2 text-xs text-red-700">{sendError}</p> : null}
      </section>
    </section>
  );
}
