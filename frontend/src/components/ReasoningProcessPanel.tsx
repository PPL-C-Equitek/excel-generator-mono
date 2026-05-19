interface ReasoningProcessPanelProps {
  readonly steps?: readonly string[];
  readonly showLoading?: boolean;
  readonly loadingText?: string;
}

const DEFAULT_LOADING_TEXT = "Loading thinking process...";

export default function ReasoningProcessPanel({
  steps = [],
  showLoading = true,
  loadingText = DEFAULT_LOADING_TEXT,
}: Readonly<ReasoningProcessPanelProps>) {
  return (
    <div data-testid="reasoning-steps">
      <p className="font-semibold text-gray-900">Reasoning steps</p>
      <div className="mt-3 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
        {steps.map((step, index) => (
          <div key={`${step}-${index}`} className="flex items-start gap-2">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-700 text-[10px] font-bold text-white">
              {index + 1}
            </span>
            <span className="whitespace-pre-wrap wrap-anywhere">{step}</span>
          </div>
        ))}

        {showLoading ? (
          <div className="flex items-center gap-2 text-red-700">
            <div className="h-2 w-2 animate-pulse rounded-full bg-red-700" />
            <span>{loadingText}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { DEFAULT_LOADING_TEXT };
