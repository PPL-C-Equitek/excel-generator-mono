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

function formatSessionDate(value: string | null) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("id-ID", {
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
          <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm leading-6">
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

        <div className="break-words overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
          <div className="max-w-full overflow-x-auto">
            <pre className="max-h-96 min-w-max overflow-auto p-4 text-xs leading-6 text-slate-100">
              <code className="break-words [overflow-wrap:anywhere]">
                {JSON.stringify(item.output_json, null, 2)}
              </code>
            </pre>
          </div>
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
        Sesi Tidak Ditemukan
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

  const userPrompts = session.history.filter(
    (item) => item.type === "message" && item.role === "user",
  ).length;
  const assistantReplies = session.history.filter(
    (item) => item.type === "message" && item.role === "assistant",
  ).length;
  const outputCount = session.history.filter((item) => item.type === "output").length;
  const firstUserPrompt = session.history.find(
    (item): item is Extract<SessionResumeHistoryItem, { type: "message" }> =>
      item.type === "message" && item.role === "user" && item.content.trim().length > 0,
  );
  const primaryPrompt = firstUserPrompt?.content ?? session.title;
  const metricCards = [
    {
      label: "Total Events",
      value: session.history.length,
      tone: "from-slate-900 to-slate-700",
    },
    {
      label: "User Prompts",
      value: userPrompts,
      tone: "from-blue-700 to-blue-500",
    },
    {
      label: "Assistant Replies",
      value: assistantReplies,
      tone: "from-emerald-700 to-emerald-500",
    },
    {
      label: "AI Outputs",
      value: outputCount,
      tone: "from-amber-700 to-amber-500",
    },
  ];

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

      <section className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
          Prompt
        </p>
        <p className="mt-2 whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm leading-6 text-slate-800">
          {primaryPrompt}
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Metadata
          </p>
          <dl className="mt-2 space-y-1 text-sm text-slate-700">
            <div className="flex justify-between gap-3">
              <dt>Created At</dt>
              <dd>{formatSessionDate(session.created_at)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Updated At</dt>
              <dd>{formatSessionDate(session.updated_at)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Last Message</dt>
              <dd>{formatSessionDate(session.last_message_at)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Last Output</dt>
              <dd>{formatSessionDate(session.last_output_at)}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Metrics
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {metricCards.map((metric) => (
              <article
                key={metric.label}
                className={`rounded-xl bg-gradient-to-br ${metric.tone} px-3 py-3 text-white shadow-sm`}
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/85">
                  {metric.label}
                </p>
                <p className="mt-2 text-2xl font-bold leading-none">{metric.value}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

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
