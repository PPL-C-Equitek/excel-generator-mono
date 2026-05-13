'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import type { AxiosError } from 'axios';
import { toast } from 'sonner';
import AuthEmailSuccessCard from '@/components/AuthEmailSuccessCard';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import {
  getRemainingResendCooldownForEmail,
  setResendCooldownForEmail,
  useResendCooldown,
} from '@/hooks/useResendCooldown';
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
  code?: string;
  message?: string;
  errors?: {
    name?: string[];
    email?: string[];
    non_field_errors?: string[];
  };
};

function FieldErrorMessage({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-800 shadow-sm">
      {children}
    </p>
  );
}

function getResendButtonText(isResending: boolean, resendCooldown: number): string {
  if (isResending) return 'Sending...';
  if (resendCooldown > 0) return `Resend (${resendCooldown}s)`;
  return 'Resend Email';
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
    errors.name = 'Name cannot be empty';
    isValid = false;
  }

  const trimmedEmail = formData.email.trim();
  if (!trimmedEmail) {
    errors.email = 'Email cannot be empty';
    isValid = false;
  } else if (!EMAIL_REGEX.test(trimmedEmail)) {
    errors.email = 'Invalid email format';
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
    successFallbackMessage: 'Verification email sent successfully.',
    errorFallbackMessage: 'Failed to resend verification email.',
    setIsSubmitting: setIsResending,
    setStatusMessage: setResendStatusMessage,
    setErrorMessage: setResendErrorMessage,
    setCooldown: setResendCooldown,
  });
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
  const { cooldown: resendCooldown, setCooldown: setResendCooldown } = useResendCooldown(
    0,
    formData.email
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (name === 'email') {
      const trimmedEmail = value.trim();
      setErrors((prev) => ({
        ...prev,
        email: trimmedEmail && !EMAIL_REGEX.test(trimmedEmail) ? 'Invalid email format' : '',
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
      const activeCooldown = getRemainingResendCooldownForEmail(trimmedEmail);

      if (activeCooldown > 0) {
        toast.success(
          'Email is not verified yet. Please check your inbox or wait until the cooldown is over.'
        );
        router.push(
          `/auth/verify-email/pending?email=${encodeURIComponent(trimmedEmail)}`
        );
        return;
      }

      const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL || ''}/auth/register/`, {
        name: formData.name,
        email: trimmedEmail,
      });

      setSuccessMessage(response.data?.message || 'Registration successful. Please check your email.');
    } catch (error: unknown) {
      const axiosError = error as AxiosError<RegisterErrorResponse>;
      const responseData = axiosError.response?.data;
      const message = responseData?.message;
      const code = responseData?.code;
      const status = axiosError.response?.status;
      const backendErrors = responseData?.errors;

      if (status === 409 && code === 'UNVERIFIED_EMAIL') {
        const emailForRedirect = formData.email.trim();
        setResendCooldownForEmail(emailForRedirect, 60);
        toast.success(
          message || 'Email is not verified yet. We have resent the verification link.'
        );
        router.push(
          `/auth/verify-email/pending?email=${encodeURIComponent(emailForRedirect)}&resent=1`
        );
        return;
      }

      if (status === 409) {
        setErrors((prev) => ({
          ...prev,
          form: 'Email is already registered, please login',
        }));
        return;
      }

      if (status === 429) {
        setErrors((prev) => ({
          ...prev,
          form: message || 'Too many attempts. Please try again in a few minutes.',
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
          form: message || 'Invalid data provided',
        }));
      } else {
        setErrors((prev) => ({
          ...prev,
          form: message || 'An error occurred on the server',
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
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      <Navbar links={LANDING_NAV_LINKS} activePage="register" />

      <main className="flex flex-1 items-center justify-center px-4 py-12">
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
              emailNotice={<>Verification email has been sent to </>}
              statusMessage={resendStatusMessage}
              errorMessage={resendErrorMessage}
              primaryHref="/login"
              primaryLabel="Go to Login Page"
              secondaryButtonText={getResendButtonText(isResending, resendCooldown)}
              onSecondaryAction={handleResendVerificationEmail}
              isSecondaryDisabled={isResending || resendCooldown > 0}
            />
          ) : (
            <form className="mt-8 space-y-6" onSubmit={handleSubmit} noValidate>
              {errors.form && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800 shadow-sm">
                  {errors.form}
                </div>
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
                    className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${
                      errors.name ? 'border-rose-400 bg-rose-50/70' : 'border-transparent'
                      }`}
                    style={{
                      backgroundColor: 'var(--surface-2)',
                      color: 'var(--foreground)',
                    }}
                  />
                  {errors.name && <FieldErrorMessage>{errors.name}</FieldErrorMessage>}
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
                    className={`relative block w-full appearance-none rounded-xl border px-4 py-3 text-sm outline-none ${
                      errors.email ? 'border-rose-400 bg-rose-50/70' : 'border-transparent'
                      }`}
                    style={{
                      backgroundColor: 'var(--surface-2)',
                      color: 'var(--foreground)',
                    }}
                  />
                  {errors.email && <FieldErrorMessage>{errors.email}</FieldErrorMessage>}
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
                  {isLoading ? 'Signing Up...' : 'Sign Up'}
                </button>
              </div>

              <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-white underline hover:text-red-50">
                  Login here
                </Link>
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
