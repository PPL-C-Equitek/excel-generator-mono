import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useSearchParams } from 'next/navigation';
import ResetPasswordPage from '../../../../src/app/auth/reset-password/page';
import { vi, describe, test, expect, beforeEach, Mock } from 'vitest';

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}));

const RESET_PASSWORD_ENDPOINT = /\/auth\/reset-password\/$/;

async function fillAndSubmitForm(password = 'Strong#123', confirmPassword = 'Strong#123') {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/^password$/i), password);
  await user.type(screen.getByLabelText(/^confirm password$/i), confirmPassword);
  await user.click(screen.getByRole('button', { name: /^reset password$/i }));
}

describe('Reset Password Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows the reset password form when token exists', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    render(<ResetPasswordPage />);

    expect(screen.getByText(/reset your password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^reset password$/i })).toBeInTheDocument();
  });

  test('shows loading state after submit while resetting password', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: vi.fn().mockResolvedValue({ message: 'Password reset successfully' }),
            } as unknown as Response);
          }, 200);
        })
    );

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    expect(screen.getByText(/resetting your password/i)).toBeInTheDocument();
    fetchSpy.mockRestore();
  });

  test('shows success state and login link on 200 OK', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Password reset successfully' }),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/password reset successfully/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /continue to login/i })).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows error immediately if no token is provided without calling API', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<ResetPasswordPage />);

    expect(screen.getByText(/reset token was not found/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('shows fallback invalid token message when API error has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('bad_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue({}),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/password reset failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows fallback invalid token message when the 400 response body is not an object', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('bad_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue(null),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/password reset failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('keeps form state and shows backend password confirmation error', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue({
        errors: { password_confirm: ['Password confirmation does not match'] },
      }),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/password confirmation does not match/i)).toBeInTheDocument();
      expect(screen.getByText(/reset your password/i)).toBeInTheDocument();
      expect(screen.queryByText(/reset failed/i)).not.toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('falls back to the invalid token message when field errors are present but not strings', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue({
        errors: { password: [123] },
      }),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/password reset failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('sends token and password fields in POST body', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('payload_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'ok' }),
    } as unknown as Response);

    render(<ResetPasswordPage />);
    await fillAndSubmitForm('Strong#123', 'Strong#123');

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringMatching(RESET_PASSWORD_ENDPOINT),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token: 'payload_token',
            password: 'Strong#123',
            password_confirm: 'Strong#123',
          }),
        })
      );
    });

    fetchSpy.mockRestore();
  });
});
