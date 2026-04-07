'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import type { AxiosError } from 'axios';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

type RegisterFormData = {
  name: string;
  email: string;
};

type RegisterFormErrors = {
  name: string;
  email: string;
  form: string;
};

type FormSubmitEvent = Parameters<NonNullable<React.ComponentProps<'form'>['onSubmit']>>[0];

type RegisterErrorResponse = {
  message?: string;
  errors?: {
    name?: string[];
    email?: string[];
    non_field_errors?: string[];
  };
};

function getResendButtonText(isResending: boolean, resendCooldown: number): string {
  if (isResending) return 'Mengirim...';
  if (resendCooldown > 0) return `Kirim Ulang (${resendCooldown}s)`;
  return 'Kirim Ulang Email';
}

export function validateRegistrationForm(formData: RegisterFormData): {
  isValid: boolean;
  errors: RegisterFormErrors;
} {
  const errors: RegisterFormErrors = {
    name: '',
    email: '',
    form: '',
  };
  let isValid = true;

  if (!formData.name.trim()) {
    errors.name = 'Nama wajib diisi';
    isValid = false;
  }

  const trimmedEmail = formData.email.trim();
  if (!trimmedEmail) {
    errors.email = 'Email wajib diisi';
    isValid = false;
  } else if (!EMAIL_REGEX.test(trimmedEmail)) {
    errors.email = 'Format email tidak valid';
    isValid = false;
  }

  return { isValid, errors };
}

export function shouldSkipResendVerification(
  email: string,
  isResending: boolean,
  resendCooldown: number
): boolean {
  return !email || isResending || resendCooldown > 0;
}

type ResendVerificationFlowParams = {
  email: string;
  isResending: boolean;
  resendCooldown: number;
  setIsResending: React.Dispatch<React.SetStateAction<boolean>>;
  setResendStatusMessage: React.Dispatch<React.SetStateAction<string>>;
  setResendErrorMessage: React.Dispatch<React.SetStateAction<string>>;
  setResendCooldown: React.Dispatch<React.SetStateAction<number>>;
};

export async function resendVerificationFlow({
  email,
  isResending,
  resendCooldown,
  setIsResending,
  setResendStatusMessage,
  setResendErrorMessage,
  setResendCooldown,
}: ResendVerificationFlowParams): Promise<void> {
  if (shouldSkipResendVerification(email, isResending, resendCooldown)) return;

  setIsResending(true);
  setResendStatusMessage('');
  setResendErrorMessage('');

  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL || ''}/auth/resend-verification/`,
      { email }
    );
    setResendStatusMessage(response.data?.message || 'Email verifikasi berhasil dikirim ulang.');
    setResendCooldown(60);
  } catch (error: unknown) {
    const axiosError = error as AxiosError<{ message?: string }>;
    setResendErrorMessage(
      axiosError.response?.data?.message || 'Gagal mengirim ulang email verifikasi.'
    );
  } finally {
    setIsResending(false);
  }
}

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState<RegisterFormData>({
    name: '',
    email: '',
  });

  const [errors, setErrors] = useState<RegisterFormErrors>({
    name: '',
    email: '',
    form: '',
  });

  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [resendStatusMessage, setResendStatusMessage] = useState('');
  const [resendErrorMessage, setResendErrorMessage] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;

    const timer = setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (name === 'email') {
      const trimmedEmail = value.trim();
      setErrors((prev) => ({
        ...prev,
        email: trimmedEmail && !EMAIL_REGEX.test(trimmedEmail) ? 'Format email tidak valid' : '',
      }));
    }
  };

  const handleSubmit = async (e: FormSubmitEvent) => {
    e.preventDefault();
    const validationResult = validateRegistrationForm(formData);
    setErrors(validationResult.errors);
    if (!validationResult.isValid) return;

    setIsLoading(true);
    setErrors((prev) => ({ ...prev, form: '' }));
    setSuccessMessage('');
    setResendErrorMessage('');
    setResendStatusMessage('');

    try {
      const trimmedEmail = formData.email.trim();
      const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL || ''}/auth/register/`, {
        name: formData.name,
        email: trimmedEmail,
      });

      setSuccessMessage(response.data?.message || 'Registrasi berhasil. Cek email Anda.');
      if (response.status === 201) {
        router.push('/login');
      }
    } catch (error: unknown) {
      const axiosError = error as AxiosError<RegisterErrorResponse>;
      const responseData = axiosError.response?.data;
      const message = responseData?.message;
      const status = axiosError.response?.status;
      const backendErrors = responseData?.errors;

      if (status === 409) {
        setErrors((prev) => ({
          ...prev,
          form: 'Email ini sudah terdaftar, silakan login',
        }));
        return;
      }

      if (status === 429) {
        setErrors((prev) => ({
          ...prev,
          form: message || 'Terlalu banyak percobaan. Coba lagi beberapa menit lagi.',
        }));
        return;
      }

      if (status === 400 && backendErrors) {
        setErrors((prev) => ({
          ...prev,
          name: backendErrors.name?.[0] || prev.name,
          email: backendErrors.email?.[0] || prev.email,
          form: backendErrors.non_field_errors?.[0] || message || '',
        }));
      } else if (status === 400) {
        setErrors((prev) => ({
          ...prev,
          form: message || 'Data yang dikirimkan tidak valid',
        }));
      } else {
        setErrors((prev) => ({
          ...prev,
          form: message || 'Terjadi kesalahan pada server',
        }));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerificationEmail = async () => {
    await resendVerificationFlow({
      email: formData.email,
      isResending,
      resendCooldown,
      setIsResending,
      setResendStatusMessage,
      setResendErrorMessage,
      setResendCooldown,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar links={LANDING_NAV_LINKS} />

      <main className="mx-auto flex w-full max-w-6xl items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-lg space-y-8 rounded-2xl p-10" style={{ backgroundColor: 'var(--brand-primary)' }}>
          <div>
            <h1 className="text-white font-bold text-2xl text-center mb-1">Register</h1>
            <p className="mt-1 text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
              Join us! Please fill in your details to create an account.
            </p>
          </div>

          {successMessage ? (
            <div className="mt-8 space-y-4">
              <div className="flex flex-col items-center gap-4 rounded-xl border border-green-200 bg-green-50 p-5 text-sm text-green-700">
                <div className="flex items-center gap-3 text-green-600">
                  <svg className="h-8 w-8 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    ></path>
                  </svg>
                  <span className="break-words text-center text-lg font-medium">{successMessage}</span>
                </div>
                <p className="text-center text-sm text-green-700">
                  Email verifikasi sudah dikirim ke <span className="font-semibold">{formData.email}</span>.
                </p>

                {resendStatusMessage && (
                  <p className="w-full rounded-md bg-green-100 px-3 py-2 text-center text-sm text-green-700">
                    {resendStatusMessage}
                  </p>
                )}
                {resendErrorMessage && (
                  <p className="w-full rounded-md bg-red-100 px-3 py-2 text-center text-sm text-red-600">
                    {resendErrorMessage}
                  </p>
                )}

                <div className="mt-2 flex w-full flex-col gap-3 sm:flex-row">
                  <Link
                    href="/login"
                    className="flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
                    style={{ color: 'var(--brand-primary)' }}
                  >
                    Pergi ke Halaman Login
                  </Link>
                  <button
                    type="button"
                    onClick={handleResendVerificationEmail}
                    disabled={isResending || resendCooldown > 0}
                    className={`w-full rounded-xl border px-4 py-3 text-sm font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${isResending || resendCooldown > 0
                      ? 'cursor-not-allowed border-gray-300 bg-gray-100 text-gray-500'
                      : 'border-red-200 bg-white text-red-700 hover:bg-red-50'
                      }`}
                    style={isResending || resendCooldown > 0 ? undefined : { color: 'var(--brand-primary)' }}
                  >
                    {getResendButtonText(isResending, resendCooldown)}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <form className="mt-8 space-y-6" onSubmit={handleSubmit} noValidate>
              {errors.form && (
                <div className="rounded-md bg-red-100 p-3 text-sm text-red-600">{errors.form}</div>
              )}

              <div className="space-y-6 force-light">
                <div>
                  <label htmlFor="name" className="mb-2 block text-sm font-bold text-white">
                    Full Name
                  </label>
                  <input
                    id="name"
                    name="name"
                    type="text"
                    value={formData.name}
                    onChange={handleChange}
                    placeholder="Enter your full name"
                    className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${errors.name ? 'border-red-300' : 'border-transparent'
                      }`}
                    style={{
                      backgroundColor: 'var(--surface-2)',
                      color: 'var(--foreground)',
                    }}
                  />
                  {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
                </div>

                <div className="force-light">
                  <label htmlFor="email" className="mb-2 block text-sm font-bold text-white">
                    Email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="Enter your email"
                    className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${errors.email ? 'border-red-300' : 'border-transparent'
                      }`}
                    style={{
                      backgroundColor: 'var(--surface-2)',
                      color: 'var(--foreground)',
                    }}
                  />
                  {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`group relative flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${isLoading ? 'cursor-not-allowed opacity-70' : ''
                    }`}
                  style={{ color: 'var(--brand-primary)' }}
                >
                  {isLoading ? 'Mendaftar...' : 'Sign Up'}
                </button>
              </div>

              <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-white underline hover:text-red-50">
                  login here
                </Link>
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
