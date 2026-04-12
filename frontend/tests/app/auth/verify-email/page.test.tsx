import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useSearchParams } from 'next/navigation';
import VerifyEmailPage from '../../../../src/app/auth/verify-email/page';
import { vi, describe, test, expect, beforeEach, Mock } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../../mocks/server';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}));

const VERIFY_EMAIL_ENDPOINT = /\/auth\/verify-email\/$/;

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

  test('Test 1 (Form): shows set password form when token exists', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    render(<VerifyEmailPage />);

    expect(screen.getByText(/set your password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /verify email and save password/i })).toBeInTheDocument();
  });

  test('Test 2 (Loading): shows loading spinner/text after submit while verifying', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, async () => {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return HttpResponse.json({ message: 'Email verified successfully' }, { status: 200 });
      })
    );

    render(<VerifyEmailPage />);

    await fillAndSubmitForm();

    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();
  });

  test('Test 1b (Suspense fallback): renders fallback when search params are pending', () => {
    (useSearchParams as Mock).mockImplementation(() => {
      throw new Promise(() => {});
    });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('Test 3 (Success): displays success message and login link on 200 OK', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json({ message: 'Email verified successfully' }, { status: 200 })
      )
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/email verified successfully/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /continue to login/i })).toBeInTheDocument();
    });
  });

  test('Test 4 (Error): displays error message on 400/404 response', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('invalid_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json({ message: 'The verification link is invalid or has expired' }, { status: 400 })
      )
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/verification link is invalid/i)).toBeInTheDocument();
    });
  });

  test('Test 5 (No Token): shows error immediately if no token is provided without calling API', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    expect(screen.getByText(/verification token was not found/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('Test 6 (Error fallback): displays default invalid/expired token message when API error has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('invalid_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () => HttpResponse.json({}, { status: 400 }))
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/verification failed\. the token is invalid or has expired\./i)
      ).toBeInTheDocument();
    });
  });

  test('Test 7 (Unknown thrown): displays generic message when thrown value is not an Error', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('broken_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockRejectedValueOnce('network-down' as never);
    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(
        screen.getByText(/something went wrong while verifying your email\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('Test 8 (Success fallback): displays default success message when API response has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('success_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () => HttpResponse.json({}, { status: 200 }))
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/your email has been verified successfully\./i)).toBeInTheDocument();
      expect(screen.getByText(/email verified/i)).toBeInTheDocument();
    });
  });

  test('Test 9 (JSON parse failure): still shows success fallback when response body cannot be parsed', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('token_parse_fail'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockRejectedValueOnce(new Error('Invalid JSON')),
    } as unknown as Response);

    render(<VerifyEmailPage />);
    await fillAndSubmitForm();

    await waitFor(() => {
      expect(screen.getByText(/your email has been verified successfully\./i)).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('Test 10 (Form validation): does not call API when password confirmation mismatches', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    await fillAndSubmitForm('Strong#123', 'Strong#124');

    expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('Test 10b (Form validation): requires password and confirmation before submit', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    await user.click(screen.getByRole('button', { name: /verify email and save password/i }));

    expect(screen.getByText(/^password is required\.$/i)).toBeInTheDocument();
    expect(screen.getByText(/^password confirmation is required\.$/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('Test 10c (Error mapping): shows nested password_confirm backend error', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json(
          { errors: { password_confirm: ['Password confirmation does not match'] } },
          { status: 400 }
        )
      )
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm('Strong#123', 'Strong#123');

    await waitFor(() => {
      expect(screen.getByText(/password confirmation does not match/i)).toBeInTheDocument();
      expect(screen.getByText(/set your password/i)).toBeInTheDocument();
      expect(screen.queryByText(/verification failed/i)).not.toBeInTheDocument();
    });
  });

  test('Test 10d (Password policy): weak password error stays on verify form', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.post(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json(
          { errors: { password: ['Password must contain at least one special character'] } },
          { status: 400 }
        )
      )
    );

    render(<VerifyEmailPage />);
    await fillAndSubmitForm('Strong123', 'Strong123');

    await waitFor(() => {
      expect(screen.getByText(/password must contain at least one special character/i)).toBeInTheDocument();
      expect(screen.getByText(/set your password/i)).toBeInTheDocument();
      expect(screen.queryByText(/verification failed/i)).not.toBeInTheDocument();
    });
  });

  test('Test 11 (API payload): sends token and password fields in POST body', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('payload_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValueOnce({ message: 'ok' }),
    } as unknown as Response);

    render(<VerifyEmailPage />);
    await fillAndSubmitForm('Strong#123', 'Strong#123');

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
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
