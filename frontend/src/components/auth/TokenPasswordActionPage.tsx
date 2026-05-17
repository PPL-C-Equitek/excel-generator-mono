'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import { useTokenPasswordAction } from '@/hooks/useTokenPasswordAction';
import {
  AuthActionLayout,
  AuthActionLink,
  AuthActionTitle,
  AuthActionFormError,
  AuthSuccessIcon,
  AuthErrorIcon,
  AuthStatusSpinner,
} from '@/components/auth/AuthActionShell';

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

function TokenPasswordActionContent({
  config,
}: Readonly<{ config: TokenPasswordActionConfig }>) {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const {
    status,
    message,
    password,
    passwordConfirm,
    errors,
    setPassword,
    setPasswordConfirm,
    handleSubmit,
  } = useTokenPasswordAction({
    token,
    endpointPath: config.endpointPath,
    validateEndpointPath: config.validateEndpointPath,
    suspenseMessage: config.suspenseMessage,
    missingTokenMessage: config.missingTokenMessage,
    invalidTokenMessage: config.invalidTokenMessage,
    unknownErrorMessage: config.unknownErrorMessage,
    loadingMessage: config.loadingMessage,
    successFallbackMessage: config.successFallbackMessage,
  });

  return (
    <AuthActionLayout Navbar={<Navbar links={LANDING_NAV_LINKS} />}>
      {status === 'form' && (
        <form className="space-y-6" onSubmit={handleSubmit} noValidate>
          <div className="space-y-2 text-center">
            <AuthActionTitle>{config.formTitle}</AuthActionTitle>
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
                className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-blue-500"
                style={{ 
                  backgroundColor: 'var(--surface-2)',
                  color: 'var(--foreground)',
                }}
              />
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
                className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:ring-2 focus:ring-blue-500"
                style={{ 
                  backgroundColor: 'var(--surface-2)',
                  color: 'var(--foreground)',
                }}
              />
              {(errors.password || errors.passwordConfirm) && (
                <AuthActionFormError>{errors.password || errors.passwordConfirm}</AuthActionFormError>
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
          <AuthStatusSpinner />
          <div className="space-y-2">
            <AuthActionTitle>{config.loadingTitle}</AuthActionTitle>
            <p className="text-sm leading-relaxed text-white/75">{message}</p>
          </div>
        </div>
      )}

      {status === 'success' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <AuthSuccessIcon />
          <div className="space-y-3">
            <AuthActionTitle>{config.successTitle}</AuthActionTitle>
            <p className="mx-auto max-w-sm text-sm leading-relaxed text-white/80">
              {message}
            </p>
          </div>
          <AuthActionLink href={config.successPrimaryHref}>
            {config.successPrimaryLabel}
          </AuthActionLink>
        </div>
      )}

      {status === 'error' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <AuthErrorIcon />
          <div className="space-y-2">
            <AuthActionTitle>{config.errorTitle}</AuthActionTitle>
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-700">
              {message}
            </div>
          </div>
          <div className="flex w-full flex-col gap-3 sm:flex-row">
            <AuthActionLink href={config.errorPrimaryHref}>
              {config.errorPrimaryLabel}
            </AuthActionLink>
            <AuthActionLink href={config.errorSecondaryHref} secondary>
              {config.errorSecondaryLabel}
            </AuthActionLink>
          </div>
        </div>
      )}
    </AuthActionLayout>
  );
}

function TokenPasswordActionLoadingFallback({
  config,
}: Readonly<{ config: TokenPasswordActionConfig }>) {
  return (
    <AuthActionLayout Navbar={<Navbar links={LANDING_NAV_LINKS} />}>
      <div className="flex flex-col items-center gap-6 text-center">
        <AuthStatusSpinner />
        <div className="space-y-2">
          <AuthActionTitle>{config.suspenseTitle}</AuthActionTitle>
          <p className="text-sm leading-relaxed text-white/75">
            {config.suspenseMessage}
          </p>
        </div>
      </div>
    </AuthActionLayout>
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
