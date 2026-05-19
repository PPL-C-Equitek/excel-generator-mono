"use client";

import { useId, useState } from "react";

interface ReasoningProcessPanelProps {
  readonly steps?: readonly string[];
  readonly showLoading?: boolean;
  readonly loadingText?: string;
}

const DEFAULT_LOADING_TEXT = "Loading thinking process...";

function ReasoningStepList({ steps }: Readonly<{ steps: readonly string[] }>) {
  return (
    <>
      {steps.map((step, index) => (
        <div key={`${step}-${index}`} className="flex items-start gap-2">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-700 text-[10px] font-bold text-white">
            {index + 1}
          </span>
          <span className="whitespace-pre-wrap wrap-anywhere">{step}</span>
        </div>
      ))}
    </>
  );
}

export default function ReasoningProcessPanel({
  steps = [],
  showLoading = true,
  loadingText = DEFAULT_LOADING_TEXT,
}: Readonly<ReasoningProcessPanelProps>) {
  return (
    <div data-testid="reasoning-steps">
      <p className="font-semibold text-gray-900">Reasoning steps</p>
      <div className="mt-3 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700">
        <ReasoningStepList steps={steps} />

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

function ChevronIcon({ isOpen }: Readonly<{ isOpen: boolean }>) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 transition-transform ${isOpen ? "rotate-180" : ""}`}
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M5 7.5L10 12.5L15 7.5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ReasoningStepsDropdown({
  steps,
}: Readonly<{ steps: readonly string[] }>) {
  const [isOpen, setIsOpen] = useState(false);
  const contentId = useId();
  const normalizedSteps = steps
    .map((step) => step.trim())
    .filter((step) => step.length > 0);

  if (normalizedSteps.length === 0) {
    return null;
  }

  return (
    <div className="mb-4" data-testid="reasoning-steps-dropdown">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left text-sm font-semibold text-gray-900 shadow-sm transition hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <span>Reasoning steps</span>
        <span className="flex items-center gap-2 text-xs font-semibold text-gray-500">
          {normalizedSteps.length}
          <ChevronIcon isOpen={isOpen} />
        </span>
      </button>

      {isOpen ? (
        <div
          id={contentId}
          className="mt-3 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700"
        >
          <ReasoningStepList steps={normalizedSteps} />
        </div>
      ) : null}
    </div>
  );
}

export { ReasoningStepsDropdown };
export { DEFAULT_LOADING_TEXT };
