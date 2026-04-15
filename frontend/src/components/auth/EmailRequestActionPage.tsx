'use client';

import React from 'react';
import Link from 'next/link';
import AuthEmailSuccessCard from '@/components/AuthEmailSuccessCard';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import {
  AuthActionLayout,
  AuthActionTitle,
} from '@/components/auth/AuthActionShell';
import { useResendCooldown } from '@/hooks/useResendCooldown';
import { resendEmailActionFlow, shouldSkipEmailResend } from '@/lib/authEmailAction';
import { type ReactNode } from 'react';

type FormSubmitEvent = Parameters<
  NonNullable<React.ComponentProps<'form'>['onSubmit']>
>[0];

type EmailErrors = {
  email: string;
  form: string;
};

export type EmailActionValidationResult = {
  isValid: boolean;
  errors: EmailErrors;
};

export interface EmailRequestActionConfig {
  pageTitle: string;
  pageDescription: string;
  emailLabel: string;
  emailPlaceholder: string;
  submitLabel: string;
  submitLoadingLabel: string;
  requestApi: (email: string) => Promise<{ message?: string }>;
  requestSuccessFallbackMessage: string;
  requestErrorFallbackMessage: string;
  resendApi: (email: string) => Promise<{ message?: string }>;
  resendCooldownStoragePrefix: string;
  resendSuccessFallbackMessage: string;
  resendErrorFallbackMessage: string;
  resendButtonLabel: (isSubmitting: boolean, cooldown: number) => string;
  resendCooldownSeconds: number;
  successEmailNotice: ReactNode;
  successPrimaryHref: string;
  successPrimaryLabel: string;
  backLinkPrefix: string;
  backLinkHref: string;
  backLinkLabel: string;
  validateEmail: (email: string) => EmailActionValidationResult;
}

function getResendCooldownStorageKey(prefix: string, email: string): string {
  return `${prefix}${email.trim().toLowerCase()}`;
}

function EmailRequestActionSuccessState({
  email,
  successMessage,
  config,
}: Readonly<{
  email: string;
  successMessage: string;
  config: EmailRequestActionConfig;
}>) {
  const [isResending, setIsResending] = React.useState(false);
  const [resendStatusMessage, setResendStatusMessage] = React.useState('');
  const [resendErrorMessage, setResendErrorMessage] = React.useState('');
  const cooldownStorageKey = getResendCooldownStorageKey(config.resendCooldownStoragePrefix, email);
  const { cooldown: resendCooldown, setCooldown: setResendCooldown } =
    useResendCooldown(0, cooldownStorageKey);

  const handleResend = async () => {
    if (shouldSkipEmailResend(email, isResending, resendCooldown)) {
      return;
    }

    await resendEmailActionFlow({
      email,
      isSubmitting: isResending,
      cooldown: resendCooldown,
      sendRequest: config.resendApi,
      successFallbackMessage: config.resendSuccessFallbackMessage,
      errorFallbackMessage: config.resendErrorFallbackMessage,
      setIsSubmitting: setIsResending,
      setStatusMessage: setResendStatusMessage,
      setErrorMessage: setResendErrorMessage,
      setCooldown: setResendCooldown,
      cooldownSeconds: config.resendCooldownSeconds,
    });
  };

  return (
    <AuthEmailSuccessCard
      successMessage={successMessage}
      email={email}
      emailNotice={config.successEmailNotice}
      statusMessage={resendStatusMessage}
      errorMessage={resendErrorMessage}
      primaryHref={config.successPrimaryHref}
      primaryLabel={config.successPrimaryLabel}
      secondaryButtonText={config.resendButtonLabel(isResending, resendCooldown)}
      onSecondaryAction={handleResend}
      isSecondaryDisabled={isResending || resendCooldown > 0}
    />
  );
}

export default function EmailRequestActionPage({
  config,
}: Readonly<{ config: EmailRequestActionConfig }>) {
  const [email, setEmail] = React.useState('');
  const [errors, setErrors] = React.useState<EmailErrors>({
    email: '',
    form: '',
  });
  const [successMessage, setSuccessMessage] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);

  const handleSubmit = async (event: FormSubmitEvent) => {
    event.preventDefault();
    const validationResult = config.validateEmail(email);

    setErrors(validationResult.errors);
    if (!validationResult.isValid) {
      return;
    }

    setIsLoading(true);
    setSuccessMessage('');
    setErrors((prev) => ({ ...prev, form: '' }));

    try {
      const response = await config.requestApi(email.trim());
      setSuccessMessage(response.message || config.requestSuccessFallbackMessage);
    } catch (error: unknown) {
      setErrors((prev) => ({
        ...prev,
        form: error instanceof Error ? error.message : config.requestErrorFallbackMessage,
      }));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthActionLayout Navbar={<Navbar links={LANDING_NAV_LINKS} />}>
      <div>
        <AuthActionTitle>{config.pageTitle}</AuthActionTitle>
        <p
          className="mt-1 text-center text-sm"
          style={{ color: 'rgba(255,255,255,0.75)' }}
        >
          {config.pageDescription}
        </p>
      </div>

      {successMessage ? (
        <EmailRequestActionSuccessState
          email={email}
          successMessage={successMessage}
          config={config}
          key={email.trim().toLowerCase()}
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
                {config.emailLabel}
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={config.emailPlaceholder}
                className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${
                  errors.email ? 'border-red-300' : 'border-transparent'
                }`}
                style={{
                  backgroundColor: 'var(--surface-2)',
                  color: 'var(--foreground)',
                }}
              />
              {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
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
              {isLoading ? config.submitLoadingLabel : config.submitLabel}
            </button>
          </div>

          <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
            {config.backLinkPrefix}{' '}
            <Link
              href={config.backLinkHref}
              className="font-semibold text-white underline hover:text-red-50"
            >
              {config.backLinkLabel}
            </Link>
          </p>
        </form>
      )}
    </AuthActionLayout>
  );
}
