'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import AuthEmailSuccessCard from '@/components/AuthEmailSuccessCard';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import { useResendCooldown } from '@/hooks/useResendCooldown';
import { requestPasswordReset, resendPasswordReset } from '@/lib/api';
import { resendEmailActionFlow, shouldSkipEmailResend } from '@/lib/authEmailAction';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
const DEFAULT_SUCCESS_MESSAGE =
  'If the email exists, we sent a reset link.';
const DEFAULT_RESEND_SUCCESS_MESSAGE = 'If the email exists, we sent a new reset link.';
const DEFAULT_RESEND_ERROR_MESSAGE = 'Failed to resend the password reset email.';
const RESEND_COOLDOWN_STORAGE_PREFIX = 'forgot-password-resend-cooldown:';

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
  return shouldSkipEmailResend(email, isResending, resendCooldown);
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
  await resendEmailActionFlow({
    email,
    isSubmitting: isResending,
    cooldown: resendCooldown,
    sendRequest: resendPasswordReset,
    successFallbackMessage: DEFAULT_RESEND_SUCCESS_MESSAGE,
    errorFallbackMessage: DEFAULT_RESEND_ERROR_MESSAGE,
    setIsSubmitting: setIsResending,
    setStatusMessage: setResendStatusMessage,
    setErrorMessage: setResendErrorMessage,
    setCooldown: setResendCooldown,
  });
}

type ForgotPasswordSuccessStateProps = {
  email: string;
  successMessage: string;
};

function ForgotPasswordSuccessState({
  email,
  successMessage,
}: Readonly<ForgotPasswordSuccessStateProps>) {
  const [isResending, setIsResending] = useState(false);
  const [resendStatusMessage, setResendStatusMessage] = useState('');
  const [resendErrorMessage, setResendErrorMessage] = useState('');
  const resendCooldownStorageKey = `${RESEND_COOLDOWN_STORAGE_PREFIX}${email
    .trim()
    .toLowerCase()}`;
  const { cooldown: resendCooldown, setCooldown: setResendCooldown } =
    useResendCooldown(0, resendCooldownStorageKey);

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
    <AuthEmailSuccessCard
      successMessage={successMessage}
      email={email}
      emailNotice={<>We sent the reset link to </>}
      statusMessage={resendStatusMessage}
      errorMessage={resendErrorMessage}
      primaryHref="/login"
      primaryLabel="Back to Login"
      secondaryButtonText={getResendButtonText(isResending, resendCooldown)}
      onSecondaryAction={handleResendPasswordReset}
      isSecondaryDisabled={isResending || resendCooldown > 0}
    />
  );
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<ForgotPasswordErrors>({
    email: '',
    form: '',
  });
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: FormSubmitEvent) => {
    event.preventDefault();

    const validationResult = validateForgotPasswordEmail(email);
    setErrors(validationResult.errors);
    if (!validationResult.isValid) return;

    setIsLoading(true);
    setSuccessMessage('');
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

  return (
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      <Navbar links={LANDING_NAV_LINKS} />

      <main className="flex flex-1 items-center justify-center px-4 py-12">
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
            <ForgotPasswordSuccessState
              key={email.trim().toLowerCase()}
              email={email}
              successMessage={successMessage}
            />
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
