'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import type { AxiosError } from 'axios';
import AuthEmailSuccessCard from '@/components/AuthEmailSuccessCard';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import { useResendCooldown } from '@/hooks/useResendCooldown';
import { resendEmailActionFlow, shouldSkipEmailResend } from '@/lib/authEmailAction';

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
  return shouldSkipEmailResend(email, isResending, resendCooldown);
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
  await resendEmailActionFlow({
    email,
    isSubmitting: isResending,
    cooldown: resendCooldown,
    sendRequest: async (trimmedEmail) => {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL || ''}/auth/resend-verification/`,
        { email: trimmedEmail }
      );
      return { message: response.data?.message };
    },
    successFallbackMessage: 'Email verifikasi berhasil dikirim ulang.',
    errorFallbackMessage: 'Gagal mengirim ulang email verifikasi.',
    setIsSubmitting: setIsResending,
    setStatusMessage: setResendStatusMessage,
    setErrorMessage: setResendErrorMessage,
    setCooldown: setResendCooldown,
  });
}

export default function RegisterPage() {
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
  const { cooldown: resendCooldown, setCooldown: setResendCooldown } = useResendCooldown();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
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
      const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL || ''}/auth/register/`, {
        name: formData.name,
        email: formData.email,
      });

      setSuccessMessage(response.data?.message || 'Registrasi berhasil. Cek email Anda.');
    } catch (error: unknown) {
      const axiosError = error as AxiosError<RegisterErrorResponse>;
      const responseData = axiosError.response?.data;
      const message = responseData?.message;
      const status = axiosError.response?.status;
      const backendErrors = responseData?.errors;

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
            <AuthEmailSuccessCard
              successMessage={successMessage}
              email={formData.email}
              emailNotice={<>Email verifikasi sudah dikirim ke </>}
              statusMessage={resendStatusMessage}
              errorMessage={resendErrorMessage}
              primaryHref="/login"
              primaryLabel="Pergi ke Halaman Login"
              secondaryButtonText={getResendButtonText(isResending, resendCooldown)}
              onSecondaryAction={handleResendVerificationEmail}
              isSecondaryDisabled={isResending || resendCooldown > 0}
            />
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
