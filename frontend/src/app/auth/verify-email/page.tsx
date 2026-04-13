'use client';

import TokenPasswordActionPage, {
  type TokenPasswordActionConfig,
} from '@/components/auth/TokenPasswordActionPage';

const verifyEmailConfig: TokenPasswordActionConfig = {
  endpointPath: '/auth/verify-email/',
  validateEndpointPath: '/auth/verify-email/validate/',
  suspenseTitle: 'Verify Email',
  suspenseMessage: 'Verifying your email...',
  missingTokenMessage: 'Verification token was not found. Please sign up again.',
  formTitle: 'Set Your Password',
  formDescription: 'Create a password to finish verifying your account.',
  submitLabel: 'Verify Email and Save Password',
  loadingTitle: 'Verify Email',
  loadingMessage: 'Verifying your email...',
  invalidTokenMessage: 'Verification failed. The token is invalid or has expired.',
  unknownErrorMessage: 'Something went wrong while verifying your email.',
  successTitle: 'Email Verified',
  successFallbackMessage: 'Your email has been verified successfully.',
  successPrimaryHref: '/login',
  successPrimaryLabel: 'Continue to Login',
  errorTitle: 'Verification Failed',
  errorPrimaryHref: '/register',
  errorPrimaryLabel: 'Back to Register',
  errorSecondaryHref: '/',
  errorSecondaryLabel: 'Back to Home',
};

export default function VerifyEmailPage() {
  return <TokenPasswordActionPage config={verifyEmailConfig} />;
}
