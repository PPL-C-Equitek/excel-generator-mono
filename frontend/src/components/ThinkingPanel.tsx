export const THINKING_PANEL_STATUS = {
  idle: "idle",
  thinking: "thinking",
  success: "success",
  error: "error",
} as const;

export type ThinkingPanelStatus =
  (typeof THINKING_PANEL_STATUS)[keyof typeof THINKING_PANEL_STATUS];

export interface ThinkingPanelProps {
  status: ThinkingPanelStatus;
  content: string;
}

const containerClassName =
  "max-h-[400px] overflow-y-auto rounded-md border border-gray-200 bg-white p-4";
const errorContainerClassName =
  "max-h-[400px] overflow-y-auto rounded-md border border-red-200 bg-red-50 p-4 text-red-700";
const panelLabel = "Proses berpikir";

export default function ThinkingPanel({
  status,
  content,
}: Readonly<ThinkingPanelProps>) {
  if (status === THINKING_PANEL_STATUS.error) {
    return (
      <div
        role="alert"
        aria-label={panelLabel}
        className={errorContainerClassName}
      >
        <p>Gagal memuat proses</p>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={panelLabel}
      className={containerClassName}
    >
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
  );
}
