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
    <div className="mt-8 space-y-4">
      <div className="flex flex-col items-center gap-4 rounded-xl border border-green-200 bg-green-50 p-5 text-sm text-green-700">
        <div className="flex items-center gap-3 text-green-600">
          <svg className="h-8 w-8 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
          <span className="break-words text-center text-lg font-medium">
            {successMessage}
          </span>
        </div>

        <p className="text-center text-sm text-green-700">
          {emailNotice}
          <span className="font-semibold">{email}</span>.
        </p>

        {statusMessage && (
          <p className="w-full rounded-md bg-green-100 px-3 py-2 text-center text-sm text-green-700">
            {statusMessage}
          </p>
        )}

        {errorMessage && (
          <p className="w-full rounded-md bg-red-100 px-3 py-2 text-center text-sm text-red-600">
            {errorMessage}
          </p>
        )}

        <div className="mt-2 flex w-full flex-col gap-3 sm:flex-row">
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
                ? 'cursor-not-allowed border-gray-300 bg-gray-100 text-gray-500'
                : 'border-red-200 bg-white text-red-700 hover:bg-red-50'
            }`}
            style={
              isSecondaryDisabled ? undefined : { color: 'var(--brand-primary)' }
            }
          >
            {secondaryButtonText}
          </button>
        </div>
      </div>
    </div>
  );
}
