import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { useSearchParams } from 'next/navigation';
import VerifyEmailPage from '@/app/auth/verify-email/page';
import { vi, describe, test, expect, beforeEach, Mock, Mocked } from 'vitest';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}));

// Mock axios
vi.mock('axios');
const mockedAxios = axios as Mocked<typeof axios>;

describe('Verify Email Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('Test 1 (Loading): shows loading spinner/text initially while verifying', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    // Never resolve the promise to keep it in loading state
    mockedAxios.get.mockImplementationOnce(() => new Promise(() => {}));

    render(<VerifyEmailPage />);

    expect(screen.getByText(/sedang memverifikasi/i)).toBeInTheDocument();
    
    await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith(expect.stringContaining('/auth/verify-email/?token=fake_token'));
    });
  });

  test('Test 2 (Success): displays success message and login link on 200 OK', async () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue('fake_token'),
    });

    mockedAxios.get.mockResolvedValueOnce({
      status: 200,
      data: { message: 'Email berhasil diverifikasi' },
    });

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

    mockedAxios.get.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { message: 'Link tidak valid atau sudah kadaluarsa' },
      },
    });

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(screen.getByText(/link tidak valid/i)).toBeInTheDocument();
    });
  });

  test('Test 4 (No Token): shows error immediately if no token is provided without calling API', () => {
    (useSearchParams as Mock).mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });

    render(<VerifyEmailPage />);
    
    expect(screen.getByText(/link tidak valid/i)).toBeInTheDocument();
    expect(mockedAxios.get).not.toHaveBeenCalled();
  });
});
