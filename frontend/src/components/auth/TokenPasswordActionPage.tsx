'use client';

import { Suspense, useEffect, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';

type ActionStatus = 'form' | 'loading' | 'success' | 'error';
type TokenFormErrors = {
  password: string;
  passwordConfirm: string;
};

type FormSubmitEvent = Parameters<NonNullable<ComponentProps<'form'>['onSubmit']>>[0];

export interface TokenPasswordActionConfig {
  endpointPath: string;
  validateEndpointPath?: string;
  suspenseTitle: string;
  suspenseMessage: string;
  missingTokenMessage: string;
  formTitle: string;
  formDescription: string;
  submitLabel: string;
  loadingTitle: string;
  loadingMessage: string;
  invalidTokenMessage: string;
  unknownErrorMessage: string;
  successTitle: string;
  successFallbackMessage: string;
  successPrimaryHref: string;
  successPrimaryLabel: string;
  errorTitle: string;
  errorPrimaryHref: string;
  errorPrimaryLabel: string;
  errorSecondaryHref: string;
  errorSecondaryLabel: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function readFirstError(errors: Record<string, unknown>, field: 'password' | 'password_confirm'): string {
  const value = errors[field];
  if (!Array.isArray(value)) {
    return '';
  }

  const firstError = value[0];
  return typeof firstError === 'string' ? firstError : '';
}

function ActionShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      <Navbar links={LANDING_NAV_LINKS} />
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div
          className="mx-auto w-full max-w-lg space-y-8 rounded-2xl p-10"
          style={{ backgroundColor: 'var(--brand-primary)' }}
        >
          {children}
        </div>
      </main>
    </div>
  );
}

function ActionTitle({ children }: Readonly<{ children: ReactNode }>) {
  return <h1 className="text-2xl font-bold text-white">{children}</h1>;
}

function FieldErrorMessage({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-800 shadow-sm">
      {children}
    </p>
  );
}

function ActionLink({
  href,
  children,
  secondary = false,
}: Readonly<{ href: string; children: ReactNode; secondary?: boolean }>) {
  return (
    <Link
      href={href}
      className={
        secondary
          ? 'inline-flex w-full items-center justify-center rounded-xl border border-white/30 bg-transparent px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2'
          : 'inline-flex w-full items-center justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold transition-all duration-200 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2'
      }
      style={secondary ? undefined : { color: 'var(--brand-primary)' }}
    >
      {children}
    </Link>
  );
}

function StatusSpinner() {
  return (
    <div className="rounded-full bg-slate-100 p-3">
      <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" />
    </div>
  );
}

function SuccessIcon() {
  return (
    <div className="rounded-full border border-white/20 bg-white/10 p-4 text-white shadow-lg shadow-red-950/20">
      <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z" />
      </svg>
    </div>
  );
}

function ErrorIcon() {
  return (
    <div className="rounded-full bg-red-100 p-3 text-red-600">
      <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    </div>
  );
}

function validatePasswordForm(password: string, passwordConfirm: string): TokenFormErrors {
  const nextErrors: TokenFormErrors = {
    password: '',
    passwordConfirm: '',
  };

  if (!password) {
    nextErrors.password = 'Password is required.';
  }

  if (!passwordConfirm) {
    nextErrors.passwordConfirm = 'Password confirmation is required.';
  } else if (password !== passwordConfirm) {
    nextErrors.passwordConfirm = 'Passwords do not match.';
  }

  return nextErrors;
}

function hasFormErrors(errors: TokenFormErrors): boolean {
  return Boolean(errors.password || errors.passwordConfirm);
}

function readMessageFromResponse(data: unknown, fallback: string): string {
  return isRecord(data) && typeof data.message === 'string'
    ? data.message
    : fallback;
}

function readFieldErrors(data: unknown): TokenFormErrors | null {
  const errorMap = isRecord(data) ? data.errors : null;
  if (!isRecord(errorMap)) {
    return null;
  }

  const nextErrors = {
    password: readFirstError(errorMap, 'password'),
    passwordConfirm: readFirstError(errorMap, 'password_confirm'),
  };

  return hasFormErrors(nextErrors) ? nextErrors : null;
}

async function submitTokenPasswordAction(
  endpointPath: string,
  token: string | null,
  password: string,
  passwordConfirm: string
): Promise<Response> {
  return fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${endpointPath}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      token,
      password,
      password_confirm: passwordConfirm,
    }),
  });
}

async function validateTokenAction(
  endpointPath: string,
  token: string | null
): Promise<Response> {
  return fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${endpointPath}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      token,
    }),
  });
}

function TokenPasswordActionContent({
  config,
}: Readonly<{ config: TokenPasswordActionConfig }>) {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<ActionStatus>(
    config.validateEndpointPath ? 'loading' : 'form'
  );
  const [message, setMessage] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<TokenFormErrors>({
    password: '',
    passwordConfirm: '',
  });

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage(config.missingTokenMessage);
    }
  }, [config.missingTokenMessage, token]);

  useEffect(() => {
    if (!config.validateEndpointPath || !token) {
      return;
    }

    let isCancelled = false;

    const checkTokenValidity = async () => {
      setStatus('loading');
      setMessage(config.suspenseMessage);

      try {
        const response = await validateTokenAction(config.validateEndpointPath!, token);
        const data = await response.json().catch(() => null);

        if (!response.ok) {
          throw new Error(readMessageFromResponse(data, config.invalidTokenMessage));
        }

        if (!isCancelled) {
          setStatus('form');
          setMessage('');
        }
      } catch (error: unknown) {
        if (!isCancelled) {
          setStatus('error');
          setMessage(
            error instanceof Error ? error.message : config.unknownErrorMessage
          );
        }
      }
    };

    void checkTokenValidity();

    return () => {
      isCancelled = true;
    };
  }, [
    config.invalidTokenMessage,
    config.suspenseMessage,
    config.unknownErrorMessage,
    config.validateEndpointPath,
    token,
  ]);

  const handleSubmit = async (event: FormSubmitEvent) => {
    event.preventDefault();

    const nextErrors = validatePasswordForm(password, passwordConfirm);
    setErrors(nextErrors);
    if (hasFormErrors(nextErrors)) {
      return;
    }

    setStatus('loading');
    setMessage(config.loadingMessage);

    try {
      const response = await submitTokenPasswordAction(
        config.endpointPath,
        token,
        password,
        passwordConfirm
      );
      const data = await response.json().catch(() => null);
      const fieldErrors = response.status === 400 ? readFieldErrors(data) : null;

      if (fieldErrors) {
        setErrors(fieldErrors);
        setStatus('form');
        return;
      }

      if (!response.ok) {
        throw new Error(readMessageFromResponse(data, config.invalidTokenMessage));
      }

      setStatus('success');
      setMessage(readMessageFromResponse(data, config.successFallbackMessage));
    } catch (error: unknown) {
      setStatus('error');
      setMessage(
        error instanceof Error ? error.message : config.unknownErrorMessage
      );
    }
  };

  return (
    <ActionShell>
      {status === 'form' && (
        <form className="space-y-6" onSubmit={handleSubmit} noValidate>
          <div className="space-y-2 text-center">
            <ActionTitle>{config.formTitle}</ActionTitle>
            <p className="text-sm leading-relaxed text-white/75">
              {config.formDescription}
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-bold text-white">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                  errors.password ? 'border-rose-400 bg-rose-50/70' : 'border-slate-300'
                }`}
                style={{ backgroundColor: '#ffffff' }}
              />
              {errors.password && <FieldErrorMessage>{errors.password}</FieldErrorMessage>}
            </div>

            <div>
              <label htmlFor="passwordConfirm" className="mb-1 block text-sm font-bold text-white">
                Confirm Password
              </label>
              <input
                id="passwordConfirm"
                name="passwordConfirm"
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                  errors.passwordConfirm ? 'border-rose-400 bg-rose-50/70' : 'border-slate-300'
                }`}
                style={{ backgroundColor: '#ffffff' }}
              />
              {errors.passwordConfirm && (
                <FieldErrorMessage>{errors.passwordConfirm}</FieldErrorMessage>
              )}
            </div>
          </div>

          <button
            type="submit"
            className="inline-flex w-full items-center justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold transition-all duration-200 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
            style={{ color: 'var(--brand-primary)' }}
          >
            {config.submitLabel}
          </button>
        </form>
      )}

      {status === 'loading' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <StatusSpinner />
          <div className="space-y-2">
            <ActionTitle>{config.loadingTitle}</ActionTitle>
            <p className="text-sm leading-relaxed text-white/75">{message}</p>
          </div>
        </div>
      )}

      {status === 'success' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <SuccessIcon />
          <div className="space-y-3">
            <ActionTitle>{config.successTitle}</ActionTitle>
            <p className="mx-auto max-w-sm text-sm leading-relaxed text-white/80">
              {message}
            </p>
          </div>
          <ActionLink href={config.successPrimaryHref}>
            {config.successPrimaryLabel}
          </ActionLink>
        </div>
      )}

      {status === 'error' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <ErrorIcon />
          <div className="space-y-2">
            <ActionTitle>{config.errorTitle}</ActionTitle>
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-700">
              {message}
            </div>
          </div>
          <div className="flex w-full flex-col gap-3 sm:flex-row">
            <ActionLink href={config.errorPrimaryHref}>
              {config.errorPrimaryLabel}
            </ActionLink>
            <ActionLink href={config.errorSecondaryHref} secondary>
              {config.errorSecondaryLabel}
            </ActionLink>
          </div>
        </div>
      )}
    </ActionShell>
  );
}

function TokenPasswordActionLoadingFallback({
  config,
}: Readonly<{ config: TokenPasswordActionConfig }>) {
  return (
    <ActionShell>
      <div className="flex flex-col items-center gap-6 text-center">
        <StatusSpinner />
        <div className="space-y-2">
          <ActionTitle>{config.suspenseTitle}</ActionTitle>
          <p className="text-sm leading-relaxed text-white/75">
            {config.suspenseMessage}
          </p>
        </div>
      </div>
    </ActionShell>
  );
}

export default function TokenPasswordActionPage({
  config,
}: Readonly<{ config: TokenPasswordActionConfig }>) {
  return (
    <Suspense fallback={<TokenPasswordActionLoadingFallback config={config} />}>
      <TokenPasswordActionContent config={config} />
    </Suspense>
  );
}
