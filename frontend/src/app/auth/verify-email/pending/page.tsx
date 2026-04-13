'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import axios from 'axios';
import Navbar from '@/components/Navbar';
import { LANDING_NAV_LINKS } from '@/constants/landing';
import { useResendCooldown } from '@/hooks/useResendCooldown';
import { resendEmailActionFlow } from '@/lib/authEmailAction';

function getResendButtonText(isResending: boolean, resendCooldown: number): string {
  if (isResending) return 'Mengirim...';
  if (resendCooldown > 0) return `Kirim Ulang (${resendCooldown}s)`;
  return 'Kirim Ulang Email';
}

export default function VerifyEmailPendingPage() {
  const searchParams = useSearchParams();
  const email = (searchParams.get('email') || '').trim();

  const [isResending, setIsResending] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const { cooldown: resendCooldown, setCooldown: setResendCooldown } =
    useResendCooldown(0, 'verify-email-pending-resend-cooldown');

  const handleResendVerificationEmail = async () => {
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
      setStatusMessage,
      setErrorMessage,
      setCooldown: setResendCooldown,
    });
  };

  return (
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      <Navbar links={LANDING_NAV_LINKS} activePage="register" />

      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div
          className="mx-auto w-full max-w-lg space-y-6 rounded-2xl p-10 text-center"
          style={{ backgroundColor: 'var(--brand-primary)' }}
        >
          <h1 className="text-white font-bold text-2xl">Cek Email Anda</h1>
          <p className="text-sm leading-relaxed text-white/90">
            Email Anda belum diverifikasi. Kami telah mengirim ulang link verifikasi. Silakan cek inbox
            dan klik link verifikasi terbaru.
          </p>
          {email && <p className="text-sm font-semibold text-white">{email}</p>}

          {statusMessage && (
            <p className="w-full rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-center text-sm text-white/85">
              {statusMessage}
            </p>
          )}

          {errorMessage && (
            <p className="w-full rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm text-red-600">
              {errorMessage}
            </p>
          )}

          <button
            type="button"
            onClick={handleResendVerificationEmail}
            disabled={!email || isResending || resendCooldown > 0}
            className={`w-full rounded-xl border px-4 py-3 text-sm font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 ${
              !email || isResending || resendCooldown > 0
                ? 'cursor-not-allowed border-white/15 bg-white/10 text-white/50'
                : 'border-white/20 bg-transparent text-white hover:bg-white/10'
            }`}
          >
            {getResendButtonText(isResending, resendCooldown)}
          </button>

          <div className="flex w-full flex-col gap-3 sm:flex-row">
            <Link
              href="/register"
              className="flex w-full justify-center rounded-xl border border-transparent bg-white px-4 py-3 text-sm font-bold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
              style={{ color: 'var(--brand-primary)' }}
            >
              Kembali ke Register
            </Link>
            <Link
              href="/login"
              className="flex w-full justify-center rounded-xl border border-white/20 bg-transparent px-4 py-3 text-sm font-bold text-white transition-colors hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2"
            >
              Ke Login
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
