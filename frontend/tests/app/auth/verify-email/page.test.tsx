import { render, screen, waitFor } from '@testing-library/react';
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

describe('Verify Email Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('Test 1 (Loading): shows loading spinner/text initially while verifying', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.get(VERIFY_EMAIL_ENDPOINT, async () => {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return HttpResponse.json({ message: 'Email berhasil diverifikasi' }, { status: 200 });
      })
    );

    render(<VerifyEmailPage />);

    expect(screen.getByText(/memverifikasi email anda/i)).toBeInTheDocument();
  });

  test('Test 2 (Success): displays success message and login link on 200 OK', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    server.use(
      http.get(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json({ message: 'Email berhasil diverifikasi' }, { status: 200 })
      )
    );

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/email berhasil diverifikasi/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /login/i })).toBeInTheDocument();
    });
  });

  test('Test 3 (Error): displays error message on 400/404 response', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('invalid_token'),
    });

    server.use(
      http.get(VERIFY_EMAIL_ENDPOINT, () =>
        HttpResponse.json({ message: 'Link tidak valid atau sudah kadaluarsa' }, { status: 400 })
      )
    );

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/link tidak valid/i)).toBeInTheDocument();
    });
  });

  test('Test 4 (No Token): shows error immediately if no token is provided without calling API', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });

    const fetchSpy = vi.spyOn(global, 'fetch');
    render(<VerifyEmailPage />);

    expect(screen.getByText(/token verifikasi tidak ditemukan/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('Test 5 (Error fallback): displays default invalid/expired token message when API error has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('invalid_token'),
    });

    server.use(
      http.get(VERIFY_EMAIL_ENDPOINT, () => HttpResponse.json({}, { status: 400 }))
    );

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/verifikasi gagal\. token tidak valid atau sudah kedaluwarsa\./i)
      ).toBeInTheDocument();
    });
  });

  test('Test 6 (Unknown thrown): displays generic message when thrown value is not an Error', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('broken_token'),
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockRejectedValueOnce('network-down' as never);
    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/terjadi kesalahan saat memverifikasi email\./i)
      ).toBeInTheDocument();
    });

    fetchSpy.mockRestore();
  });

  test('Test 7 (Success fallback): displays default success message when API response has no message', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('success_token'),
    });

    server.use(
      http.get(VERIFY_EMAIL_ENDPOINT, () => HttpResponse.json({}, { status: 200 }))
    );

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/email anda berhasil diverifikasi\./i)).toBeInTheDocument();
      expect(screen.getByText(/verifikasi berhasil/i)).toBeInTheDocument();
    });
  });
});
