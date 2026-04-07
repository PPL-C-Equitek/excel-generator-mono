import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ForgotPasswordPage, {
  resendPasswordResetFlow,
  shouldSkipPasswordResetResend,
  validateForgotPasswordEmail,
} from '../../../src/app/forgot-password/page';
import { requestPasswordReset, resendPasswordReset } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  requestPasswordReset: vi.fn(),
  resendPasswordReset: vi.fn(),
}));

describe('forgot password helpers', () => {
  it('requires an email address', () => {
    expect(validateForgotPasswordEmail('   ')).toEqual({
      isValid: false,
      errors: {
        email: 'Email is required.',
        form: '',
      },
    });
  });

  it('rejects an invalid email address', () => {
    expect(validateForgotPasswordEmail('invalid-email')).toEqual({
      isValid: false,
      errors: {
        email: 'Please enter a valid email address.',
        form: '',
      },
    });
  });

  it('allows resend when there is an email and no active resend guard', () => {
    expect(shouldSkipPasswordResetResend('user@example.com', false, 0)).toBe(false);
  });

  it('skips resend when the request is already in flight', () => {
    expect(shouldSkipPasswordResetResend('user@example.com', true, 0)).toBe(true);
  });

  it('resend flow exits early when the guard blocks it', async () => {
    const setIsResending = vi.fn();
    const setResendStatusMessage = vi.fn();
    const setResendErrorMessage = vi.fn();
    const setResendCooldown = vi.fn();

    await resendPasswordResetFlow({
      email: '',
      isResending: false,
      resendCooldown: 0,
      setIsResending,
      setResendStatusMessage,
      setResendErrorMessage,
      setResendCooldown,
    });

    expect(resendPasswordReset).not.toHaveBeenCalled();
    expect(setIsResending).not.toHaveBeenCalled();
  });
});

describe('ForgotPasswordPage', () => {
  afterEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
  });

  it('renders the forgot password form', () => {
    render(<ForgotPasswordPage />);

    expect(screen.getByRole('heading', { name: /forgot password/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /send reset link/i })
    ).toBeInTheDocument();
  });

  it('does not submit when the email is empty', async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordPage />);

    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(requestPasswordReset).not.toHaveBeenCalled();
    expect(screen.getByText('Email is required.')).toBeInTheDocument();
  });

  it('submits the email and shows the success state', async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValueOnce({
      message: 'Password reset link sent.',
    });

    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith('user@example.com');
    });

    expect(screen.getByText('Password reset link sent.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to login/i })).toBeInTheDocument();
  });

  it('uses the fallback success message when the API returns no message', async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValueOnce({});

    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(
      await screen.findByText(
        'If an account exists for this email, we have sent a password reset link.'
      )
    ).toBeInTheDocument();
  });

  it('shows the request error when the API rejects', async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockRejectedValueOnce(
      new Error('Unable to send reset link.')
    );

    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByText('Unable to send reset link.')).toBeInTheDocument();
  });

  it('resends the password reset email and starts the cooldown', async () => {
    vi.mocked(requestPasswordReset).mockResolvedValueOnce({
      message: 'Password reset link sent.',
    });
    vi.mocked(resendPasswordReset).mockResolvedValueOnce({
      message: 'Password reset link sent again.',
    });

    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    await screen.findByText('Password reset link sent.');

    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /resend email/i }));
      await Promise.resolve();
    });

    expect(resendPasswordReset).toHaveBeenCalledWith('user@example.com');

    expect(screen.getByText('Password reset link sent again.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resend \(60s\)/i })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /resend \(60s\)/i }));
    expect(resendPasswordReset).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByRole('button', { name: /resend \(59s\)/i })).toBeDisabled();
  });

  it('uses the fallback resend error message for non-Error failures', async () => {
    const user = userEvent.setup();
    vi.mocked(requestPasswordReset).mockResolvedValueOnce({
      message: 'Password reset link sent.',
    });
    vi.mocked(resendPasswordReset).mockRejectedValueOnce('unexpected');

    render(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));
    await screen.findByText('Password reset link sent.');

    await user.click(screen.getByRole('button', { name: /resend email/i }));

    expect(
      await screen.findByText('Failed to resend the password reset email.')
    ).toBeInTheDocument();
  });
});
