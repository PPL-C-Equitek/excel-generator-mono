import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { useRouter } from 'next/navigation';
import RegisterPage, {
  shouldSkipResendVerification,
  resendVerificationFlow,
} from '@/app/register/page';

import { vi, describe, test, expect, beforeEach, afterEach, Mock, Mocked } from 'vitest';

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

// Mock axios
vi.mock('axios');
const mockedAxios = axios as Mocked<typeof axios>;

describe('Registration Page', () => {
  const mockPush = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useRouter as Mock).mockReturnValue({ push: mockPush });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const setup = () => {
    render(<RegisterPage />);
    return {
      nameInput: screen.getByLabelText(/nama lengkap/i) as HTMLInputElement,
      emailInput: screen.getByLabelText(/email/i) as HTMLInputElement,
      passwordInput: screen.getByLabelText(/^password/i) as HTMLInputElement,
      confirmPasswordInput: screen.getByLabelText(/konfirmasi password/i) as HTMLInputElement,
      submitBtn: screen.getByRole('button', { name: /daftar/i }),
    };
  };

  describe('resend guard helper', () => {
    test('returns true when email is empty', () => {
      expect(shouldSkipResendVerification('', false, 0)).toBe(true);
    });

    test('returns true when request is in-flight', () => {
      expect(shouldSkipResendVerification('user@example.com', true, 0)).toBe(true);
    });

    test('returns true when cooldown is active', () => {
      expect(shouldSkipResendVerification('user@example.com', false, 10)).toBe(true);
    });

    test('returns false when resend should proceed', () => {
      expect(shouldSkipResendVerification('user@example.com', false, 0)).toBe(false);
    });

    test('resend flow exits early when guard is true', async () => {
      const setIsResending = vi.fn();
      const setResendStatusMessage = vi.fn();
      const setResendErrorMessage = vi.fn();
      const setResendCooldown = vi.fn();

      await resendVerificationFlow({
        email: '',
        isResending: false,
        resendCooldown: 0,
        setIsResending,
        setResendStatusMessage,
        setResendErrorMessage,
        setResendCooldown,
      });

      expect(mockedAxios.post).not.toHaveBeenCalled();
      expect(setIsResending).not.toHaveBeenCalled();
      expect(setResendStatusMessage).not.toHaveBeenCalled();
      expect(setResendErrorMessage).not.toHaveBeenCalled();
      expect(setResendCooldown).not.toHaveBeenCalled();
    });
  });

  test('1. renders all required fields and submit button', () => {
    const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();

    expect(nameInput).toBeInTheDocument();
    expect(emailInput).toBeInTheDocument();
    expect(passwordInput).toBeInTheDocument();
    expect(confirmPasswordInput).toBeInTheDocument();
    expect(submitBtn).toBeInTheDocument();
  });

  describe('2. Client-Side Validation', () => {
    test('shows required error messages if fields are empty upon submission', async () => {
      const { submitBtn } = setup();

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/nama wajib diisi/i)).toBeInTheDocument();
        expect(screen.getByText(/email wajib diisi/i)).toBeInTheDocument();
        expect(screen.getByText(/password wajib diisi/i)).toBeInTheDocument();
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    test('shows error if email format is invalid', async () => {
      const { emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      await user.type(emailInput, 'invalid-email');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/format email tidak valid/i)).toBeInTheDocument();
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    test('shows error if password and confirm password do not match', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      await user.type(nameInput, 'John Doe');
      await user.type(emailInput, 'john@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'DifferentPass123!');
      
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/password tidak cocok/i)).toBeInTheDocument();
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    test('shows error if password is less than 8 characters', async () => {
      const { passwordInput, submitBtn } = setup();
      const user = userEvent.setup();

      await user.type(passwordInput, '1234567');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/password minimal 8 karakter/i)).toBeInTheDocument();
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
  });

  describe('3. API Integration and 4. Loading State', () => {
    test('successful registration shows success message and rendering resend and login links', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'John Doe');
      await user.type(emailInput, 'john@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      // 4. Loading State (button text changes and becomes disabled while API is in-flight)
      expect(submitBtn).toHaveTextContent(/mendaftar\.\.\./i);
      expect(submitBtn).toBeDisabled();

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/auth/register/'), {
          name: 'John Doe',
          email: 'john@example.com',
          password: 'SecurePass123!',
        });
      });

      // 3. Success Feedback -> shows resend CTA and login link
      await waitFor(() => {
        expect(screen.getByText(/cek email anda/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /kirim ulang email/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /pergi ke halaman login/i })).toBeInTheDocument();
      });
    });

    test('successful resend verification triggers success message toast', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      // First, mock the registration
      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'Resend User');
      await user.type(emailInput, 'resend@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      // Wait for the Resend button to appear
      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

      // Mock the resend verification endpoint
      mockedAxios.post.mockResolvedValueOnce({
        status: 200,
        data: { message: 'Email verifikasi telah dikirim ulang' },
      });

      fireEvent.click(resendBtn);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/auth/resend-verification/'), {
          email: 'resend@example.com',
        });
        expect(screen.getByText(/email verifikasi telah dikirim ulang/i)).toBeInTheDocument();
      });
    });

    test('resend failure shows fallback error message when API response has no message', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'Resend Fail User');
      await user.type(emailInput, 'resendfail@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 500,
          data: {},
        },
      });

      fireEvent.click(resendBtn);

      await waitFor(() => {
        expect(screen.getByText(/gagal mengirim ulang email verifikasi\./i)).toBeInTheDocument();
      });
    });

    test('resend cooldown decreases every second after successful resend', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      const setIntervalSpy = vi
        .spyOn(global, 'setInterval')
        .mockImplementation(((callback: TimerHandler) => {
          if (typeof callback === 'function') {
            for (let i = 0; i < 70; i += 1) {
              callback();
            }
          }
          return 1 as unknown as ReturnType<typeof setInterval>;
        }) as typeof setInterval);
      const clearIntervalSpy = vi
        .spyOn(global, 'clearInterval')
        .mockImplementation(() => undefined);

      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'Cooldown User');
      await user.type(emailInput, 'cooldown@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');
      fireEvent.click(submitBtn);

      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

      mockedAxios.post.mockResolvedValueOnce({
        status: 200,
        data: { message: 'Email verifikasi telah dikirim ulang' },
      });

      fireEvent.click(resendBtn);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /kirim ulang \(/i })).toBeInTheDocument();
      });

      expect(setIntervalSpy).toHaveBeenCalled();
      expect(clearIntervalSpy).toHaveBeenCalled();

      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    });

    test('resend success uses fallback message when response has no message', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'Resend Fallback User');
      await user.type(emailInput, 'resendfallback@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');
      fireEvent.click(submitBtn);

      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

      mockedAxios.post.mockResolvedValueOnce({
        status: 200,
        data: {},
      });

      fireEvent.click(resendBtn);

      await waitFor(() => {
        expect(screen.getByText(/email verifikasi berhasil dikirim ulang\./i)).toBeInTheDocument();
      });
    });

    test('resend ignores second click while request is in-flight (guard branch)', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 201,
        data: { message: 'Cek email Anda' },
      });

      await user.type(nameInput, 'Resend Guard User');
      await user.type(emailInput, 'resendguard@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');
      fireEvent.click(submitBtn);

      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

      let resolveResend: ((value: { status: number; data: { message: string } }) => void) | undefined;
      mockedAxios.post.mockImplementationOnce(
        () =>
          new Promise<{ status: number; data: { message: string } }>((resolve) => {
            resolveResend = resolve;
          })
      );

      fireEvent.click(resendBtn);
      const loadingBtn = await screen.findByRole('button', { name: /mengirim\.\.\./i });
      loadingBtn.removeAttribute('disabled');
      loadingBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      expect(mockedAxios.post).toHaveBeenCalledTimes(2);

      resolveResend?.({ status: 200, data: { message: 'Email verifikasi telah dikirim ulang' } });
      await waitFor(() => {
        expect(screen.getByText(/email verifikasi telah dikirim ulang/i)).toBeInTheDocument();
      });

      // still 2 calls: register + first resend only
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });



    test('shows error when email already exists (409 Conflict)', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 409,
          data: { message: 'Email sudah terdaftar' },
        },
      });

      await user.type(nameInput, 'Existing User');
      await user.type(emailInput, 'existing@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/email sudah terdaftar/i)).toBeInTheDocument();
      });
    });

    test('shows error when data is invalid (400 Bad Request)', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: { message: 'Data yang dikirimkan tidak valid' },
        },
      });

      await user.type(nameInput, 'Invalid User');
      await user.type(emailInput, 'invalid@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/data yang dikirimkan tidak valid/i)).toBeInTheDocument();
      });
    });

    test('shows generic error on 500 Server Error', async () => {
      const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 500,
          data: { message: 'Terjadi kesalahan pada server' },
        },
      });

      await user.type(nameInput, 'Server Error User');
      await user.type(emailInput, 'error@example.com');
      await user.type(passwordInput, 'SecurePass123!');
      await user.type(confirmPasswordInput, 'SecurePass123!');

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/terjadi kesalahan pada server/i)).toBeInTheDocument();
      });
      
      // Ensure loading state is reverted when failure occurs
      expect(submitBtn).toHaveTextContent(/daftar/i);
      expect(submitBtn).not.toBeDisabled();
    });

    describe('Fallback Messages', () => {
      test('shows fallback message on 201 when no data.message is provided', async () => {
        const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
        const user = userEvent.setup();
        mockedAxios.post.mockResolvedValueOnce({ status: 201, data: {} });
        await user.type(nameInput, 'New'); await user.type(emailInput, 'new@example.com'); await user.type(passwordInput, 'Secure123!'); await user.type(confirmPasswordInput, 'Secure123!');
        fireEvent.click(submitBtn);
        await waitFor(() => expect(screen.getByText(/Registrasi berhasil. Cek email Anda./i)).toBeInTheDocument());
      });

      test('shows fallback message on 409 when no data.message is provided', async () => {
        const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
        const user = userEvent.setup();
        mockedAxios.post.mockRejectedValueOnce({ response: { status: 409, data: {} } });
        await user.type(nameInput, 'Existing'); await user.type(emailInput, 'exist@example.com'); await user.type(passwordInput, 'Secure123!'); await user.type(confirmPasswordInput, 'Secure123!');
        fireEvent.click(submitBtn);
        await waitFor(() => expect(screen.getByText(/Email sudah terdaftar/i)).toBeInTheDocument());
      });

      test('shows fallback message on 400 when no data.message is provided', async () => {
        const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
        const user = userEvent.setup();
        mockedAxios.post.mockRejectedValueOnce({ response: { status: 400, data: {} } });
        await user.type(nameInput, 'Invalid'); await user.type(emailInput, 'inv@example.com'); await user.type(passwordInput, 'Secure123!'); await user.type(confirmPasswordInput, 'Secure123!');
        fireEvent.click(submitBtn);
        await waitFor(() => expect(screen.getByText(/Data yang dikirimkan tidak valid/i)).toBeInTheDocument());
      });

      test('shows fallback message on 500 when no data.message is provided', async () => {
        const { nameInput, emailInput, passwordInput, confirmPasswordInput, submitBtn } = setup();
        const user = userEvent.setup();
        mockedAxios.post.mockRejectedValueOnce({ response: { status: 500, data: {} } });
        await user.type(nameInput, 'Server'); await user.type(emailInput, 'serv@example.com'); await user.type(passwordInput, 'Secure123!'); await user.type(confirmPasswordInput, 'Secure123!');
        fireEvent.click(submitBtn);
        await waitFor(() => expect(screen.getByText(/Terjadi kesalahan pada server/i)).toBeInTheDocument());
      });
    });
  });
});
