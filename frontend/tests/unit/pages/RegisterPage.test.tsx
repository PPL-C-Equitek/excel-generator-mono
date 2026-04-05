import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { useRouter } from 'next/navigation';
import { useGoogleLogin } from '@react-oauth/google';
import RegisterPage, {
  shouldSkipResendVerification,
  resendVerificationFlow,
} from '@/app/register/page';

import { vi, describe, test, expect, beforeEach, afterEach, Mock, Mocked } from 'vitest';

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

vi.mock('@react-oauth/google', () => ({
  useGoogleLogin: vi.fn(),
}));

vi.mock('axios');
const mockedAxios = axios as Mocked<typeof axios>;
const mockedUseGoogleLogin = useGoogleLogin as Mock;

describe('Registration Page', () => {
  const mockPush = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useRouter as Mock).mockReturnValue({ push: mockPush });
    mockedUseGoogleLogin.mockReturnValue(vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const setup = () => {
    render(<RegisterPage />);
    return {
      nameInput: screen.getByLabelText(/nama lengkap/i) as HTMLInputElement,
      emailInput: screen.getByLabelText(/email/i) as HTMLInputElement,
      submitBtn: screen.getByRole('button', { name: /daftar sekarang/i }),
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

  test('renders required fields and submit button without password inputs', () => {
    const { nameInput, emailInput, submitBtn } = setup();

    expect(nameInput).toBeInTheDocument();
    expect(emailInput).toBeInTheDocument();
    expect(submitBtn).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign up with google/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /login here/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/^password$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/konfirmasi password/i)).not.toBeInTheDocument();
  });

  describe('client-side validation', () => {
    test('shows required error messages if fields are empty on submit', async () => {
      const { submitBtn } = setup();

      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/nama wajib diisi/i)).toBeInTheDocument();
        expect(screen.getByText(/email wajib diisi/i)).toBeInTheDocument();
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
  });

  describe('API integration and loading state', () => {
    test('successful registration posts only name/email and shows success block', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 200,
        data: { message: 'Jika email valid, link verifikasi telah dikirim ke kotak masuk Anda.' },
      });

      await user.type(nameInput, 'John Doe');
      await user.type(emailInput, 'john@example.com');

      fireEvent.click(submitBtn);

      expect(submitBtn).toHaveTextContent(/mendaftar\.\.\./i);
      expect(submitBtn).toBeDisabled();

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(expect.stringContaining('/auth/register/'), {
          name: 'John Doe',
          email: 'john@example.com',
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/jika email valid/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /kirim ulang email/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /pergi ke halaman login/i })).toBeInTheDocument();
      });
    });

    test('success fallback message is shown when response has no message', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({ status: 200, data: {} });

      await user.type(nameInput, 'New User');
      await user.type(emailInput, 'new@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/registrasi berhasil\. cek email anda\./i)).toBeInTheDocument();
      });
    });

    test('successful resend verification shows success message', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({
        status: 200,
        data: { message: 'Registrasi berhasil' },
      });

      await user.type(nameInput, 'Resend User');
      await user.type(emailInput, 'resend@example.com');
      fireEvent.click(submitBtn);

      const resendBtn = await screen.findByRole('button', { name: /kirim ulang email/i });

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

    test('resend failure uses fallback error message when API has no message', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({ status: 200, data: { message: 'ok' } });

      await user.type(nameInput, 'Resend Fail User');
      await user.type(emailInput, 'resendfail@example.com');
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
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      const setIntervalSpy = vi
        .spyOn(global, 'setInterval')
        .mockImplementation(((callback: TimerHandler) => {
          if (typeof callback === 'function') {
            for (let i = 0; i < 70; i += 1) {
              (callback as () => void)();
            }
          }
          return 1 as unknown as ReturnType<typeof setInterval>;
        }) as unknown as typeof setInterval);
      const clearIntervalSpy = vi
        .spyOn(global, 'clearInterval')
        .mockImplementation(() => undefined);

      mockedAxios.post.mockResolvedValueOnce({ status: 200, data: { message: 'ok' } });

      await user.type(nameInput, 'Cooldown User');
      await user.type(emailInput, 'cooldown@example.com');
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
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({ status: 200, data: { message: 'ok' } });

      await user.type(nameInput, 'Resend Fallback User');
      await user.type(emailInput, 'resendfallback@example.com');
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
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockResolvedValueOnce({ status: 200, data: { message: 'ok' } });

      await user.type(nameInput, 'Resend Guard User');
      await user.type(emailInput, 'resendguard@example.com');
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

      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
    });

    test('shows error when data is invalid (400 Bad Request)', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: { message: 'Data yang dikirimkan tidak valid' },
        },
      });

      await user.type(nameInput, 'Invalid User');
      await user.type(emailInput, 'invalid@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/data yang dikirimkan tidak valid/i)).toBeInTheDocument();
      });
    });

    test('shows generic error on 500 Server Error', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 500,
          data: { message: 'Terjadi kesalahan pada server' },
        },
      });

      await user.type(nameInput, 'Server Error User');
      await user.type(emailInput, 'error@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/terjadi kesalahan pada server/i)).toBeInTheDocument();
      });

      expect(submitBtn).toHaveTextContent(/daftar sekarang/i);
      expect(submitBtn).not.toBeDisabled();
    });

    test('shows rate limit fallback message on 429 when no data.message is provided', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 429,
          data: {},
        },
      });

      await user.type(nameInput, 'Rate User');
      await user.type(emailInput, 'rate@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/terlalu banyak percobaan/i)).toBeInTheDocument();
      });
    });

    test('maps backend serializer field errors on 400 response', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            errors: {
              email: ['Format email tidak valid dari backend'],
              non_field_errors: ['Terjadi kesalahan validasi umum'],
            },
          },
        },
      });

      await user.type(nameInput, 'Field Error User');
      await user.type(emailInput, 'fielderror@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/format email tidak valid dari backend/i)).toBeInTheDocument();
        expect(screen.getByText(/terjadi kesalahan validasi umum/i)).toBeInTheDocument();
      });
    });

    test('uses message fallback when non_field_errors is missing in 400 serializer errors', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            message: 'Fallback message dari backend',
            errors: {
              name: ['Nama backend tidak valid'],
            },
          },
        },
      });

      await user.type(nameInput, 'Fallback User');
      await user.type(emailInput, 'fallback@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/nama backend tidak valid/i)).toBeInTheDocument();
        expect(screen.getByText(/fallback message dari backend/i)).toBeInTheDocument();
      });
    });

    test('keeps form message empty when 400 serializer errors have no non_field_errors and no message', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            errors: {
              name: ['Nama backend invalid kosong message'],
            },
          },
        },
      });

      await user.type(nameInput, 'Empty Msg User');
      await user.type(emailInput, 'emptymessage@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/nama backend invalid kosong message/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/fallback message dari backend/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/data yang dikirimkan tidak valid/i)).not.toBeInTheDocument();
    });

    test('shows fallback message on 400 when no data.message is provided', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({ response: { status: 400, data: {} } });

      await user.type(nameInput, 'Invalid');
      await user.type(emailInput, 'inv@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => expect(screen.getByText(/data yang dikirimkan tidak valid/i)).toBeInTheDocument());
    });

    test('shows fallback message on 500 when no data.message is provided', async () => {
      const { nameInput, emailInput, submitBtn } = setup();
      const user = userEvent.setup();

      mockedAxios.post.mockRejectedValueOnce({ response: { status: 500, data: {} } });

      await user.type(nameInput, 'Server');
      await user.type(emailInput, 'serv@example.com');
      fireEvent.click(submitBtn);

      await waitFor(() => expect(screen.getByText(/terjadi kesalahan pada server/i)).toBeInTheDocument());
    });
  });
});
