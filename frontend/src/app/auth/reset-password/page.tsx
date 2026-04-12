'use client';

import TokenPasswordActionPage, {
  type TokenPasswordActionConfig,
} from '@/components/auth/TokenPasswordActionPage';

const resetPasswordConfig: TokenPasswordActionConfig = {
  endpointPath: '/auth/reset-password/',
  suspenseTitle: 'Reset Password',
  suspenseMessage: 'Loading your reset link...',
  missingTokenMessage: 'Reset token was not found. Please request a new password reset email.',
  formTitle: 'Reset Your Password',
  formDescription: 'Enter a new password to finish resetting your account.',
  submitLabel: 'Reset Password',
  loadingTitle: 'Reset Password',
  loadingMessage: 'Resetting your password...',
  invalidTokenMessage: 'Password reset failed. The token is invalid or has expired.',
  unknownErrorMessage: 'Something went wrong while resetting your password.',
  successTitle: 'Password Reset',
  successFallbackMessage: 'Your password has been reset successfully.',
  successPrimaryHref: '/login',
  successPrimaryLabel: 'Continue to Login',
  errorTitle: 'Reset Failed',
  errorPrimaryHref: '/forgot-password',
  errorPrimaryLabel: 'Request a New Link',
  errorSecondaryHref: '/',
  errorSecondaryLabel: 'Back to Home',
};

export default function ResetPasswordPage() {
  return <TokenPasswordActionPage config={resetPasswordConfig} />;
}
