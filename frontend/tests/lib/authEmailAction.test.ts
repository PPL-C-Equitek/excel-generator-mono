import { describe, expect, it, vi } from 'vitest';
import { resendEmailActionFlow } from '@/lib/authEmailAction';

describe('resendEmailActionFlow', () => {
  it('uses the fallback error message for non-Error failures', async () => {
    const setIsSubmitting = vi.fn();
    const setStatusMessage = vi.fn();
    const setErrorMessage = vi.fn();
    const setCooldown = vi.fn();

    await resendEmailActionFlow({
      email: 'user@example.com',
      isSubmitting: false,
      cooldown: 0,
      sendRequest: vi.fn().mockRejectedValue('unexpected'),
      successFallbackMessage: 'sent',
      errorFallbackMessage: 'fallback error',
      setIsSubmitting,
      setStatusMessage,
      setErrorMessage,
      setCooldown,
    });

    expect(setErrorMessage).toHaveBeenCalledWith('fallback error');
    expect(setIsSubmitting).toHaveBeenNthCalledWith(1, true);
    expect(setIsSubmitting).toHaveBeenLastCalledWith(false);
  });
});
