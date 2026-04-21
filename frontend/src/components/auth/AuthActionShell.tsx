import Link from 'next/link';
import type { ReactNode } from 'react';

export function AuthActionShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-lg space-y-8 rounded-2xl p-10">
          {children}
        </div>
      </main>
    </div>
  );
}

export function AuthActionLayout({
  children,
  Navbar,
}: Readonly<{ children: ReactNode; Navbar: ReactNode }>) {
  return (
    <div className="force-light min-h-screen bg-gray-50 flex flex-col">
      {Navbar}
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div
          className="mx-auto w-full max-w-lg space-y-8 rounded-2xl p-10"
          style={{ backgroundColor: 'var(--brand-primary)' }}
        >
          {children}
        </div>
      </main>
    </div>
  );
}

export function AuthActionTitle({ children }: Readonly<{ children: ReactNode }>) {
  return <h1 className="text-2xl font-bold text-white">{children}</h1>;
}

export function AuthActionFormError({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-800 shadow-sm">
      {children}
    </p>
  );
}

export function AuthActionLink({
  href,
  children,
  secondary = false,
  className = '',
}: Readonly<{
  href: string;
  children: ReactNode;
  secondary?: boolean;
  className?: string;
}>) {
  return (
    <Link
      href={href}
      className={
        secondary
          ? 'inline-flex w-full items-center justify-center rounded-xl border border-white/30 bg-transparent px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2'
          : 'inline-flex w-full items-center justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold transition-all duration-200 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2'
      }
      style={secondary ? undefined : { color: 'var(--brand-primary)' }}
    >
      <span className={className}>{children}</span>
    </Link>
  );
}

export function AuthStatusSpinner() {
  return (
    <div className="rounded-full bg-slate-100 p-3">
      <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-red-600" />
    </div>
  );
}

export function AuthSuccessIcon() {
  return (
    <div className="rounded-full border border-white/20 bg-white/10 p-4 text-white shadow-lg shadow-red-950/20">
      <svg
        className="h-16 w-16"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z"
        />
      </svg>
    </div>
  );
}

export function AuthErrorIcon() {
  return (
    <div className="rounded-full bg-red-100 p-3 text-red-600">
      <svg
        className="h-16 w-16"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
        />
      </svg>
    </div>
  );
}
