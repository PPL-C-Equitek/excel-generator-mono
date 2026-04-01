'use client';

import { Suspense, useEffect, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

type VerifyStatus = 'form' | 'loading' | 'success' | 'error';

type VerifyFormErrors = {
  password: string;
  passwordConfirm: string;
};

type FormSubmitEvent = Parameters<NonNullable<ComponentProps<'form'>['onSubmit']>>[0];

function PageShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-white to-slate-100 px-4 py-8">
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
        <div className="w-full max-w-lg rounded-2xl border border-slate-200/80 bg-white p-10 shadow-2xl shadow-slate-300/40">
          {children}
        </div>
      </div>
    </div>
  );
}

function StateTitle({ children, tone }: Readonly<{ children: ReactNode; tone: 'neutral' | 'success' | 'error' }>) {
  const toneClass = {
    neutral: 'text-slate-900',
    success: 'text-green-700',
    error: 'text-red-700',
  }[tone];

  return <h1 className={`text-3xl font-extrabold tracking-tight ${toneClass}`}>{children}</h1>;
}

function PrimaryButton({ href, children }: Readonly<{ href: string; children: ReactNode }>) {
  return (
    <Link
      href={href}
      className="inline-flex w-full items-center justify-center rounded-xl bg-red-700 px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
    >
      {children}
    </Link>
  );
}

function SecondaryButton({ href, children }: Readonly<{ href: string; children: ReactNode }>) {
  return (
    <Link
      href={href}
      className="inline-flex w-full items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition-all duration-200 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
    >
      {children}
    </Link>
  );
}

function VerifyEmailLoadingFallback() {
  return (
    <PageShell>
      <div className="flex flex-col items-center gap-6 text-center">
        <div className="rounded-full bg-slate-100 p-3">
          <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" />
        </div>
        <div className="space-y-2">
          <StateTitle tone="neutral">Verifikasi Email</StateTitle>
          <p className="text-sm leading-relaxed text-slate-600">Memverifikasi email Anda...</p>
        </div>
      </div>
    </PageShell>
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<VerifyStatus>('form');
  const [message, setMessage] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [errors, setErrors] = useState<VerifyFormErrors>({
    password: '',
    passwordConfirm: '',
  });

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Token verifikasi tidak ditemukan. Silakan registrasi ulang.');
    }
  }, [token]);

  const handleSubmit = async (event: FormSubmitEvent) => {
    event.preventDefault();

    const nextErrors: VerifyFormErrors = {
      password: '',
      passwordConfirm: '',
    };

    if (!password) {
      nextErrors.password = 'Password wajib diisi';
    }
    if (!passwordConfirm) {
      nextErrors.passwordConfirm = 'Konfirmasi password wajib diisi';
    } else if (password !== passwordConfirm) {
      nextErrors.passwordConfirm = 'Password tidak cocok';
    }

    setErrors(nextErrors);
    if (nextErrors.password || nextErrors.passwordConfirm) return;

    setStatus('loading');
    setMessage('Memverifikasi email Anda...');

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || ''}/auth/verify-email/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token,
            password,
            password_confirm: passwordConfirm,
          }),
        }
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        if (response.status === 400 && data?.errors) {
          setErrors({
            password: data.errors.password?.[0] || '',
            passwordConfirm: data.errors.password_confirm?.[0] || '',
          });
          setStatus('form');
          return;
        }

        const errorMessage = data?.message;
        throw new Error(errorMessage || 'Verifikasi gagal. Token tidak valid atau sudah kedaluwarsa.');
      }

      setStatus('success');
      setMessage(data?.message || 'Email Anda berhasil diverifikasi.');
    } catch (error: unknown) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Terjadi kesalahan saat memverifikasi email.');
    }
  };

  return (
    <PageShell>
      {status === 'form' && (
        <form className="space-y-6" onSubmit={handleSubmit} noValidate>
          <div className="space-y-2 text-center">
            <StateTitle tone="neutral">Set Password Anda</StateTitle>
            <p className="text-sm leading-relaxed text-slate-600">
              Masukkan password baru untuk menyelesaikan verifikasi akun.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                  errors.password ? 'border-red-300' : 'border-slate-300'
                }`}
              />
              {errors.password && <p className="mt-1 text-sm text-red-600">{errors.password}</p>}
            </div>

            <div>
              <label htmlFor="passwordConfirm" className="mb-1 block text-sm font-medium text-slate-700">
                Konfirmasi Password
              </label>
              <input
                id="passwordConfirm"
                name="passwordConfirm"
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                className={`w-full rounded-xl border px-4 py-3 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-red-500 ${
                  errors.passwordConfirm ? 'border-red-300' : 'border-slate-300'
                }`}
              />
              {errors.passwordConfirm && (
                <p className="mt-1 text-sm text-red-600">{errors.passwordConfirm}</p>
              )}
            </div>
          </div>

          <button
            type="submit"
            className="inline-flex w-full items-center justify-center rounded-xl bg-red-700 px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          >
            Verifikasi dan Simpan Password
          </button>
        </form>
      )}

      {status === 'loading' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="rounded-full bg-slate-100 p-3">
            <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" />
          </div>
          <div className="space-y-2">
            <StateTitle tone="neutral">Verifikasi Email</StateTitle>
            <p className="text-sm leading-relaxed text-slate-600">{message}</p>
          </div>
        </div>
      )}

      {status === 'success' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="rounded-full bg-green-100 p-3 text-green-600">
            <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <div className="space-y-2">
            <StateTitle tone="success">Verifikasi Berhasil</StateTitle>
            <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm leading-relaxed text-green-700">
              {message}
            </div>
          </div>
          <PrimaryButton href="/login">Lanjut ke Login</PrimaryButton>
        </div>
      )}

      {status === 'error' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="rounded-full bg-red-100 p-3 text-red-600">
            <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <div className="space-y-2">
            <StateTitle tone="error">Verifikasi Gagal</StateTitle>
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-700">
              {message}
            </div>
          </div>
          <div className="flex w-full flex-col gap-3 sm:flex-row">
            <PrimaryButton href="/register">Ke Register</PrimaryButton>
            <SecondaryButton href="/">Ke Beranda</SecondaryButton>
          </div>
        </div>
      )}
    </PageShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<VerifyEmailLoadingFallback />}>
      <VerifyEmailContent />
    </Suspense>
  );
}
