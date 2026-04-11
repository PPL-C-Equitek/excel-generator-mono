import type React from 'react';

type MessageResponse = {
  message?: string;
};

type SetState<T> = React.Dispatch<React.SetStateAction<T>>;

export function shouldSkipEmailResend(
  email: string,
  isSubmitting: boolean,
  cooldown: number
): boolean {
  return !email.trim() || isSubmitting || cooldown > 0;
}

type ResendEmailFlowParams = {
  email: string;
  isSubmitting: boolean;
  cooldown: number;
  sendRequest: (email: string) => Promise<MessageResponse>;
  successFallbackMessage: string;
  errorFallbackMessage: string;
  setIsSubmitting: SetState<boolean>;
  setStatusMessage: SetState<string>;
  setErrorMessage: SetState<string>;
  setCooldown: SetState<number>;
  cooldownSeconds?: number;
};

export async function resendEmailActionFlow({
  email,
  isSubmitting,
  cooldown,
  sendRequest,
  successFallbackMessage,
  errorFallbackMessage,
  setIsSubmitting,
  setStatusMessage,
  setErrorMessage,
  setCooldown,
  cooldownSeconds = 60,
}: ResendEmailFlowParams): Promise<void> {
  if (shouldSkipEmailResend(email, isSubmitting, cooldown)) return;

  setIsSubmitting(true);
  setStatusMessage('');
  setErrorMessage('');

  try {
    const response = await sendRequest(email.trim());
    setStatusMessage(response.message || successFallbackMessage);
    setCooldown(cooldownSeconds);
  } catch (error: unknown) {
    setErrorMessage(
      error instanceof Error ? error.message : errorFallbackMessage
    );
  } finally {
    setIsSubmitting(false);
  }
}
