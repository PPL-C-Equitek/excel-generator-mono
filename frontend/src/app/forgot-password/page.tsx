'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import { requestPasswordReset, resendPasswordReset } from '@/lib/api';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
const DEFAULT_SUCCESS_MESSAGE =
  'If an account exists for this email, we have sent a password reset link.';
const DEFAULT_RESEND_SUCCESS_MESSAGE = 'Password reset email sent again.';
const DEFAULT_RESEND_ERROR_MESSAGE = 'Failed to resend the password reset email.';

type ForgotPasswordErrors = {
  email: string;
  form: string;
};

type FormSubmitEvent = Parameters<
  NonNullable<React.ComponentProps<'form'>['onSubmit']>
>[0];

function getResendButtonText(isResending: boolean, resendCooldown: number): string {
  if (isResending) return 'Sending...';
  if (resendCooldown > 0) return `Resend (${resendCooldown}s)`;
  return 'Resend Email';
}

export function validateForgotPasswordEmail(email: string): {
  isValid: boolean;
  errors: ForgotPasswordErrors;
} {
  const trimmedEmail = email.trim();
  const errors: ForgotPasswordErrors = {
    email: '',
    form: '',
  };

  if (!trimmedEmail) {
    errors.email = 'Email is required.';
    return { isValid: false, errors };
  }

  if (!EMAIL_REGEX.test(trimmedEmail)) {
    errors.email = 'Please enter a valid email address.';
    return { isValid: false, errors };
  }

  return { isValid: true, errors };
}

export function shouldSkipPasswordResetResend(
  email: string,
  isResending: boolean,
  resendCooldown: number
): boolean {
  return !email.trim() || isResending || resendCooldown > 0;
}

type ResendPasswordResetFlowParams = {
  email: string;
  isResending: boolean;
  resendCooldown: number;
  setIsResending: React.Dispatch<React.SetStateAction<boolean>>;
  setResendStatusMessage: React.Dispatch<React.SetStateAction<string>>;
  setResendErrorMessage: React.Dispatch<React.SetStateAction<string>>;
  setResendCooldown: React.Dispatch<React.SetStateAction<number>>;
};

export async function resendPasswordResetFlow({
  email,
  isResending,
  resendCooldown,
  setIsResending,
  setResendStatusMessage,
  setResendErrorMessage,
  setResendCooldown,
}: ResendPasswordResetFlowParams): Promise<void> {
  if (shouldSkipPasswordResetResend(email, isResending, resendCooldown)) return;

  setIsResending(true);
  setResendStatusMessage('');
  setResendErrorMessage('');

  try {
    const response = await resendPasswordReset(email.trim());
    setResendStatusMessage(response.message || DEFAULT_RESEND_SUCCESS_MESSAGE);
    setResendCooldown(60);
  } catch (error: unknown) {
    setResendErrorMessage(
      error instanceof Error ? error.message : DEFAULT_RESEND_ERROR_MESSAGE
    );
  } finally {
    setIsResending(false);
  }
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<ForgotPasswordErrors>({
    email: '',
    form: '',
  });
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [resendStatusMessage, setResendStatusMessage] = useState('');
  const [resendErrorMessage, setResendErrorMessage] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;

    const timer = setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [resendCooldown]);

  const handleSubmit = async (event: FormSubmitEvent) => {
    event.preventDefault();

    const validationResult = validateForgotPasswordEmail(email);
    setErrors(validationResult.errors);
    if (!validationResult.isValid) return;

    setIsLoading(true);
    setSuccessMessage('');
    setResendStatusMessage('');
    setResendErrorMessage('');
    setErrors((prev) => ({ ...prev, form: '' }));

    try {
      const response = await requestPasswordReset(email.trim());
      setSuccessMessage(response.message || DEFAULT_SUCCESS_MESSAGE);
    } catch (error: unknown) {
      setErrors((prev) => ({
        ...prev,
        form: error instanceof Error ? error.message : 'Something went wrong.',
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendPasswordReset = async () => {
    await resendPasswordResetFlow({
      email,
      isResending,
      resendCooldown,
      setIsResending,
      setResendStatusMessage,
      setResendErrorMessage,
      setResendCooldown,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar links={LANDING_NAV_LINKS} />

      <main className="mx-auto flex w-full max-w-6xl items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div
          className="mx-auto w-full max-w-lg space-y-8 rounded-2xl p-10"
          style={{ backgroundColor: 'var(--brand-primary)' }}
        >
          <div>
            <h1 className="text-white font-bold text-2xl text-center mb-1">
              Forgot Password
            </h1>
            <p
              className="mt-1 text-center text-sm"
              style={{ color: 'rgba(255,255,255,0.75)' }}
            >
              Enter your email and we&apos;ll send you a password reset link.
            </p>
          </div>

          {successMessage ? (
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
                  We sent the reset link to <span className="font-semibold">{email}</span>.
                </p>

                {resendStatusMessage && (
                  <p className="w-full rounded-md bg-green-100 px-3 py-2 text-center text-sm text-green-700">
                    {resendStatusMessage}
                  </p>
                )}

                {resendErrorMessage && (
                  <p className="w-full rounded-md bg-red-100 px-3 py-2 text-center text-sm text-red-600">
                    {resendErrorMessage}
                  </p>
                )}

                <div className="mt-2 flex w-full flex-col gap-3 sm:flex-row">
                  <Link
                    href="/login"
                    className="flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
                    style={{ color: 'var(--brand-primary)' }}
                  >
                    Back to Login
                  </Link>
                  <button
                    type="button"
                    onClick={handleResendPasswordReset}
                    disabled={isResending || resendCooldown > 0}
                    className={`w-full rounded-xl border px-4 py-3 text-sm font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${
                      isResending || resendCooldown > 0
                        ? 'cursor-not-allowed border-gray-300 bg-gray-100 text-gray-500'
                        : 'border-red-200 bg-white text-red-700 hover:bg-red-50'
                    }`}
                    style={
                      isResending || resendCooldown > 0
                        ? undefined
                        : { color: 'var(--brand-primary)' }
                    }
                  >
                    {getResendButtonText(isResending, resendCooldown)}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <form className="mt-8 space-y-6" onSubmit={handleSubmit} noValidate>
              {errors.form && (
                <div className="rounded-md bg-red-100 p-3 text-sm text-red-600">
                  {errors.form}
                </div>
              )}

              <div className="space-y-6 force-light">
                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-bold text-white">
                    Email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="Enter your email"
                    className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${
                      errors.email ? 'border-red-300' : 'border-transparent'
                    }`}
                    style={{
                      backgroundColor: 'var(--surface-2)',
                      color: 'var(--foreground)',
                    }}
                  />
                  {errors.email && (
                    <p className="mt-1 text-sm text-red-600">{errors.email}</p>
                  )}
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`group relative flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${
                    isLoading ? 'cursor-not-allowed opacity-70' : ''
                  }`}
                  style={{ color: 'var(--brand-primary)' }}
                >
                  {isLoading ? 'Sending...' : 'Send Reset Link'}
                </button>
              </div>

              <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Remembered your password?{' '}
                <Link href="/login" className="font-semibold text-white underline hover:text-red-50">
                  Back to login
                </Link>
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
