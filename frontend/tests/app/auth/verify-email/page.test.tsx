import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useSearchParams } from 'next/navigation';
import VerifyEmailPage from '../../../../src/app/auth/verify-email/page';
import { vi, describe, test, expect, beforeEach, Mock } from 'vitest';

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}));

const VERIFY_EMAIL_ENDPOINT = /\/auth\/verify-email\/$/;
const VERIFY_EMAIL_VALIDATE_ENDPOINT = /\/auth\/verify-email\/validate\/$/;

async function fillAndSubmitForm(password = 'Strong#123', confirmPassword = 'Strong#123') {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/^password$/i), password);
  await user.type(screen.getByLabelText(/^confirm password$/i), confirmPassword);
  await user.click(screen.getByRole('button', { name: /verify email and save password/i }));
}

describe('Verify Email Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows suspense fallback while search params are still resolving', async () => {
    let hasResolved = false;
    const searchParamsPromise = Promise.resolve().then(() => {
      hasResolved = true;
    });

    (useSearchParams as Mock).mockImplementation(() => {
      if (!hasResolved) {
        throw searchParamsPromise;
      }

      return { get: vi.fn().mockReturnValue('suspense_token') };
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);

    expect(screen.getByText(/verify email/i)).toBeInTheDocument();
    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/set your password/i)).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows set password form only after token validation succeeds', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('fake_token') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);

    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();
    expect(await screen.findByText(/set your password/i)).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringMatching(VERIFY_EMAIL_VALIDATE_ENDPOINT),
      expect.objectContaining({ body: JSON.stringify({ token: 'fake_token' }) })
    );

    fetchSpy.mockRestore();
  });

  test('shows immediate error when validation fails before form render', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('invalid_token') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue({}),
    } as unknown as Response);

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/verification failed\. the token is invalid or has expired\./i)).toBeInTheDocument();
    });

    expect(screen.queryByText(/set your password/i)).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  test('shows already verified message for reused token', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('used_token') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockResolvedValue({ message: 'Email is already verified' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/email is already verified/i)).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows error immediately if no token is provided without calling API', () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue(null) });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    expect(screen.getByText(/verification token was not found/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('shows success state after valid validation and submit', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('success_token') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Email verified successfully' }),
      } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/email verified successfully/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /continue to login/i })).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows success fallback when submit response has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('success_fallback') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/your email has been verified successfully\./i)).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('keeps form state and maps backend field errors on submit', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('field_error_token') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: vi.fn().mockResolvedValue({
          errors: { password_confirm: ['Password confirmation does not match'] },
        }),
      } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/password confirmation does not match/i)).toBeInTheDocument();
      expect(screen.getByText(/set your password/i)).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('does not call submit endpoint when password confirmation mismatches', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('mismatch_token') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm('Strong#123', 'Strong#124');

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  test('shows required field errors when password inputs are left empty', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('required_token') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /verify email and save password/i }));

    expect(screen.getByText(/password is required\./i)).toBeInTheDocument();
    expect(screen.getByText(/password confirmation is required\./i)).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  test('shows unknown validation fallback when validation throws a non-error value', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('unknown_validation') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockRejectedValueOnce('unexpected failure');

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/something went wrong while verifying your email\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('falls back to the invalid token message when validation returns unreadable json', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('bad_json_validation') });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: vi.fn().mockRejectedValue(new Error('bad json')),
    } as unknown as Response);

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/verification failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('shows unknown submit fallback when submit throws a non-error value', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('unknown_submit') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockRejectedValueOnce('unexpected failure');

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/something went wrong while verifying your email\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('falls back to the invalid token message when submit returns unreadable json', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('bad_json_submit') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: vi.fn().mockRejectedValue(new Error('bad json')),
      } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/verification failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('does not switch state after unmount when validation resolves late', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('late_success') });

    let resolveResponse: ((value: Response) => void) | undefined;
    const fetchSpy = vi.spyOn(global, 'fetch').mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve;
        })
    );

    const { unmount } = render(<VerifyEmailPage />);
    unmount();

    resolveResponse?.({
      ok: true,
      json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
    } as unknown as Response);

    await Promise.resolve();
    await Promise.resolve();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  test('does not switch state after unmount when validation fails late', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('late_failure') });

    let rejectResponse: ((reason?: unknown) => void) | undefined;
    const fetchSpy = vi.spyOn(global, 'fetch').mockImplementationOnce(
      () =>
        new Promise<Response>((_, reject) => {
          rejectResponse = reject;
        })
    );

    const { unmount } = render(<VerifyEmailPage />);
    unmount();

    rejectResponse?.(new Error('late failure'));

    await Promise.resolve();
    await Promise.resolve();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  test('sends token to validate endpoint and password payload to verify endpoint', async () => {
    (useSearchParams as Mock).mockReturnValue({ get: vi.fn().mockReturnValue('payload_token') });

    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'Verification token is valid' }),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({ message: 'ok' }),
      } as unknown as Response);

    render(<VerifyEmailPage />);
    await screen.findByText(/set your password/i);
    await fillAndSubmitForm('Strong#123', 'Strong#123');

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenNthCalledWith(
        1,
        expect.stringMatching(VERIFY_EMAIL_VALIDATE_ENDPOINT),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: 'payload_token' }),
        })
      );

      expect(fetchSpy).toHaveBeenNthCalledWith(
        2,
        expect.stringMatching(VERIFY_EMAIL_ENDPOINT),
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
