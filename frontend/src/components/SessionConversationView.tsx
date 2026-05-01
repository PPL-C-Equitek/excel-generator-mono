import ThinkingPanel, { THINKING_PANEL_STATUS } from "@/components/ThinkingPanel";
import type { SessionResume, SessionResumeHistoryItem } from "@/services/sessions";
import type { ThinkingLogItem } from "@/services/thinkingLogs";

interface SessionConversationViewProps {
  readonly session: SessionResume | null;
  readonly isLoadingSession: boolean;
  readonly sessionError: string | null;
  readonly isSessionNotFound: boolean;
  readonly thinkingLogsByOutputId: Record<string, ThinkingLogItem>;
  readonly isLoadingThinkingLogs: boolean;
  readonly thinkingLogsError: string | null;
}

function formatHistoryTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
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

  if (thinkingLogsError && !content) {
    return (
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.error}
        content=""
      />
    );
  }

  if (isLoadingThinkingLogs && !content) {
    return (
      <ThinkingPanel
        status={THINKING_PANEL_STATUS.loading}
        content=""
        animated
      />
    );
  }

  return (
    <ThinkingPanel
      status={THINKING_PANEL_STATUS.success}
      content={content}
    />
  );
}

function SessionHistoryBubble({
  item,
  thinkingLogRecord,
  isLoadingThinkingLogs,
  thinkingLogsError,
}: {
  readonly item: SessionResumeHistoryItem;
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
          className={`max-w-3xl rounded-3xl px-4 py-3 shadow-sm ${
            isAssistant
              ? "bg-slate-100 text-slate-900"
              : "bg-red-700 text-white"
          }`}
        >
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
            {isAssistant ? "Assistant" : "User"}
          </p>
          <p className="whitespace-pre-wrap break-words text-sm leading-6">
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
      <div className="max-w-4xl space-y-3 rounded-3xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          AI Output
        </p>

        {renderThinkingPanelForOutput(
          item,
          thinkingLogRecord,
          isLoadingThinkingLogs,
          thinkingLogsError,
        )}

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
          <pre className="max-h-96 overflow-auto p-4 text-xs leading-6 text-slate-100">
            {JSON.stringify(item.output_json, null, 2)}
          </pre>
        </div>

        <p className="text-[11px] text-slate-500">
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
        Session tidak ditemukan untuk history ini.
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

  return (
    <section className="space-y-5" aria-labelledby="session-conversation-title">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
          Session View
        </p>
        <h2 id="session-conversation-title" className="text-xl font-bold text-slate-900">
          {session.title}
        </h2>
        <p className="text-sm text-slate-500">{session.id}</p>
        {thinkingLogsError ? (
          <p className="text-sm text-red-700">{thinkingLogsError}</p>
        ) : null}
      </header>

      <div className="space-y-4">
        {session.history.map((item) => (
          <SessionHistoryBubble
            key={`${item.type}-${item.id}`}
            item={item}
            thinkingLogRecord={item.type === "output" ? thinkingLogsByOutputId[item.id] : undefined}
            isLoadingThinkingLogs={isLoadingThinkingLogs}
            thinkingLogsError={thinkingLogsError}
          />
        ))}
      </div>
    </section>
  );
}
