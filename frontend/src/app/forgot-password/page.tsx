'use client';

import React from 'react';
import EmailRequestActionPage, {
  type EmailRequestActionConfig,
} from '@/components/auth/EmailRequestActionPage';
import { resendEmailActionFlow, shouldSkipEmailResend } from '@/lib/authEmailAction';
import { requestPasswordReset, resendPasswordReset } from '@/lib/api';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
const DEFAULT_SUCCESS_MESSAGE = 'If the email exists, we sent a reset link.';
const DEFAULT_RESEND_SUCCESS_MESSAGE = 'If the email exists, we sent a new reset link.';
const DEFAULT_RESEND_ERROR_MESSAGE = 'Failed to resend the password reset email.';
const DEFAULT_ERROR_MESSAGE = 'Something went wrong.';
const RESEND_COOLDOWN_STORAGE_PREFIX = 'forgot-password-resend-cooldown:';

type ForgotPasswordErrors = {
  email: string;
  form: string;
};

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

function getResendButtonText(isResending: boolean, resendCooldown: number): string {
  if (isResending) return 'Sending...';
  if (resendCooldown > 0) return `Resend (${resendCooldown}s)`;
  return 'Resend Email';
}

const FORGOT_PASSWORD_ACTION_CONFIG: EmailRequestActionConfig = {
  pageTitle: 'Forgot Password',
  pageDescription: "Enter your email and we'll send you a password reset link.",
  emailLabel: 'Email',
  emailPlaceholder: 'Enter your email',
  submitLabel: 'Send Reset Link',
  submitLoadingLabel: 'Sending...',
  requestApi: requestPasswordReset,
  requestSuccessFallbackMessage: DEFAULT_SUCCESS_MESSAGE,
  requestErrorFallbackMessage: DEFAULT_ERROR_MESSAGE,
  resendApi: resendPasswordReset,
  resendCooldownStoragePrefix: RESEND_COOLDOWN_STORAGE_PREFIX,
  resendSuccessFallbackMessage: DEFAULT_RESEND_SUCCESS_MESSAGE,
  resendErrorFallbackMessage: DEFAULT_RESEND_ERROR_MESSAGE,
  resendButtonLabel: getResendButtonText,
  resendCooldownSeconds: 60,
  successEmailNotice: <>We sent the reset link to </>,
  successPrimaryHref: '/login',
  successPrimaryLabel: 'Back to Login',
  backLinkPrefix: 'Remembered your password?',
  backLinkHref: '/login',
  backLinkLabel: 'Back to login',
  validateEmail: validateForgotPasswordEmail,
};

export default function ForgotPasswordPage() {
  return <EmailRequestActionPage config={FORGOT_PASSWORD_ACTION_CONFIG} />;
}
