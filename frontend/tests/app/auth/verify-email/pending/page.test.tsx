import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { useSearchParams } from 'next/navigation';
import VerifyEmailPendingPage from '@/app/auth/verify-email/pending/page';
import { vi, describe, test, expect, beforeEach, Mocked, Mock } from 'vitest';

vi.mock('axios');
vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}));

const mockedAxios = axios as Mocked<typeof axios>;

describe('Verify Email Pending Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.sessionStorage.clear();
  });

  test('renders email from query and enables resend button', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('pending@example.com'),
    });

    render(<VerifyEmailPendingPage />);

    expect(screen.getByText('pending@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /kirim ulang/i })).toBeEnabled();
  });

  test('resend verification calls API and shows success status', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('pending@example.com'),
    });

    mockedAxios.post.mockResolvedValueOnce({
      data: { message: 'Email verifikasi telah dikirim ulang' },
    } as never);

    render(<VerifyEmailPendingPage />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /kirim ulang/i }));

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/auth/resend-verification/'),
        { email: 'pending@example.com' }
      );
      expect(screen.getByText(/email verifikasi telah dikirim ulang/i)).toBeInTheDocument();
    });
  });

  test('disables resend button when email query is missing', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });

    render(<VerifyEmailPendingPage />);

    expect(screen.queryByText('pending@example.com')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /kirim ulang/i })).toBeDisabled();
  });

  test('shows resend error message when request fails', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('pending@example.com'),
    });

    mockedAxios.post.mockRejectedValueOnce(new Error('Mail service down'));

    render(<VerifyEmailPendingPage />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /kirim ulang/i }));

    await waitFor(() => {
      expect(screen.getByText(/mail service down/i)).toBeInTheDocument();
    });
  });
});
