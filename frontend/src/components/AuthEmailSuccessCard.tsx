import Link from 'next/link';
import type React from 'react';

interface AuthEmailSuccessCardProps {
  readonly successMessage: string;
  readonly email: string;
  readonly emailNotice: React.ReactNode;
  readonly statusMessage?: string;
  readonly errorMessage?: string;
  readonly primaryHref: string;
  readonly primaryLabel: string;
  readonly secondaryButtonText: string;
  readonly onSecondaryAction: () => void;
  readonly isSecondaryDisabled: boolean;
}

export default function AuthEmailSuccessCard({
  successMessage,
  email,
  emailNotice,
  statusMessage,
  errorMessage,
  primaryHref,
  primaryLabel,
  secondaryButtonText,
  onSecondaryAction,
  isSecondaryDisabled,
}: AuthEmailSuccessCardProps) {
  return (
    <div className="mt-8 space-y-6">
      <div className="flex flex-col items-center gap-5 text-center">
        <div className="rounded-full border border-white/20 bg-white/10 p-4 text-white shadow-lg shadow-red-950/20">
          <svg className="h-14 w-14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z"
            />
          </svg>
        </div>

        <div className="space-y-3">
          <p className="mx-auto max-w-md text-sm leading-relaxed text-white/90">
            {successMessage}
          </p>
          <p className="mx-auto max-w-sm text-sm leading-relaxed text-white/75">
            {emailNotice}
            <span className="font-semibold text-white">{email}</span>.
          </p>
        </div>

        {statusMessage && (
          <p className="w-full rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-center text-sm text-white/85">
            {statusMessage}
          </p>
        )}

        {errorMessage && (
          <p className="w-full rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm text-red-600">
            {errorMessage}
          </p>
        )}

        <div className="flex w-full flex-col gap-3 sm:flex-row">
          <Link
            href={primaryHref}
            className="flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
            style={{ color: 'var(--brand-primary)' }}
          >
            {primaryLabel}
          </Link>
          <button
            type="button"
            onClick={onSecondaryAction}
            disabled={isSecondaryDisabled}
            className={`w-full rounded-xl border px-4 py-3 text-sm font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${
              isSecondaryDisabled
                ? 'cursor-not-allowed border-white/15 bg-white/10 text-white/50'
                : 'border-white/20 bg-transparent text-white hover:bg-white/10'
            }`}
          >
            {secondaryButtonText}
          </button>
        </div>
      </div>
    </div>
  );
}
