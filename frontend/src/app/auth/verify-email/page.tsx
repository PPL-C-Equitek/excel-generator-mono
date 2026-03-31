'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

type VerifyStatus = 'loading' | 'success' | 'error';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<VerifyStatus>('loading');
  const [message, setMessage] = useState('Memverifikasi email Anda...');

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) {
        setStatus('error');
        setMessage('Token verifikasi tidak ditemukan. Silakan registrasi ulang.');
        return;
      }

      setStatus('loading');
      setMessage('Memverifikasi email Anda...');

      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || ''}/auth/verify-email/?token=${encodeURIComponent(token)}`,
          { method: 'GET' }
        );
        const data = await response.json().catch(() => null);

        if (!response.ok) {
          throw new Error(data?.message || 'Verifikasi gagal. Token tidak valid atau sudah kedaluwarsa.');
        }

        setStatus('success');
        setMessage(data?.message || 'Email Anda berhasil diverifikasi.');
      } catch (error: unknown) {
        setStatus('error');
        setMessage(
          error instanceof Error
            ? error.message
            : 'Terjadi kesalahan saat memverifikasi email.'
        );
      }
    };

    verifyEmail();
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 via-white to-slate-100 px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl shadow-slate-300/40">
        {status === 'loading' && (
          <div className="flex flex-col items-center gap-5 text-center">
            <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" />
            <h1 className="text-2xl font-bold text-slate-900">Verifikasi Email</h1>
            <p className="text-sm text-slate-600">{message}</p>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col items-center gap-5 text-center">
            <div className="rounded-full bg-green-100 p-3 text-green-600">
              <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z" />
              </svg>
            </div>
            <h1 className="text-3xl font-extrabold text-green-700">Verifikasi Berhasil</h1>
            <p className="text-sm text-slate-600">{message}</p>
            <Link
              href="/login"
              className="mt-1 inline-flex w-full items-center justify-center rounded-md bg-red-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
            >
              Lanjut ke Login
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-5 text-center">
            <div className="rounded-full bg-red-100 p-3 text-red-600">
              <svg className="h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            </div>
            <h1 className="text-3xl font-extrabold text-red-700">Verifikasi Gagal</h1>
            <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{message}</p>
            <div className="flex w-full gap-3">
              <Link
                href="/register"
                className="inline-flex w-full items-center justify-center rounded-md bg-red-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                Ke Register
              </Link>
              <Link
                href="/"
                className="inline-flex w-full items-center justify-center rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-2"
              >
                Ke Beranda
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
