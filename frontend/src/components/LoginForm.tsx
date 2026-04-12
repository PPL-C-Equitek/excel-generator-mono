'use client'

import { useState } from 'react'

export interface LoginFormData {
    email: string
    password: string
}

interface LoginFormProps {
    onSubmit?: (data: LoginFormData) => void
    onGoogleSignIn?: () => void
}

export default function LoginForm({ onSubmit, onGoogleSignIn }: Readonly<LoginFormProps>) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = () => {
        setError(null)

        // Batasi panjang email
        if (!email || email.length > 254) {
            setError('Please enter a valid email address.')
            return
        }

        // Validasi email
        const emailRegex = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+$/
        if (!emailRegex.test(email)) {
            setError('Please enter a valid email address.')
            return
        }

        // Validasi password
        if (!password) {
            setError('Password is required.')
            return
        }

        onSubmit?.({ email, password })
    }

    return (
        <div
            className="rounded-2xl p-10 w-full max-w-lg mx-auto"
            style={{ backgroundColor: 'var(--brand-primary)' }}
        >
            {/* Heading */}
            <h1 className="text-white font-bold text-2xl text-center mb-1">Login</h1>
            <p className="text-center text-sm mb-6" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Sign in to continue to your workspace.
            </p>

            {/* Error */}
            {error && (
                <div
                    role="alert"
                    className="mb-4 rounded-lg border p-3 text-sm"
                    style={{
                        backgroundColor: 'var(--danger-bg)',
                        borderColor: 'var(--danger-border)',
                        color: 'var(--danger-text)',
                    }}
                >
                    {error}
                </div>
            )}

            {/* Email */}
            <div className="mb-4">
                <label
                    htmlFor="email"
                    className="block text-white font-bold text-sm mb-2"
                >
                    Email
                </label>
                <input
                    id="email"
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                    style={{
                        backgroundColor: 'var(--surface-2)',
                        color: 'var(--foreground)',
                    }}
                />
            </div>

            {/* Password */}
            <div className="mb-4">
                <label
                    htmlFor="password"
                    className="block text-white font-bold text-sm mb-2"
                >
                    Password
                </label>
                <input
                    id="password"
                    data-testid="password-input"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                    style={{
                        backgroundColor: 'var(--surface-2)',
                        color: 'var(--foreground)',
                    }}
                />
            </div>

            {/* Forgot password */}
            <div className="flex items-center justify-between mb-6">
                <a
                    href="/forgot-password"
                    className="text-white font-bold text-sm hover:underline"
                >
                    Forgot Password?
                </a>
            </div>

            {/* Sign in */}
            <button
                onClick={handleSubmit}
                className="w-full py-3 rounded-xl font-bold text-sm mb-3 transition active:scale-[0.98]"
                style={{ backgroundColor: '#ffffff', color: 'var(--brand-primary)' }}
            >
                Sign In
            </button>

            {/* Sign in with Google */}
            <button
                type="button"
                onClick={() => onGoogleSignIn?.()}
                className="w-full py-3 rounded-xl font-bold text-sm mb-6 flex items-center justify-center gap-2 transition active:scale-[0.98]"
                style={{ backgroundColor: '#ffffff', color: '#111827' }}
            >
                <span className="text-base">G</span>{' '}
                Sign In with Google
            </button>

            {/* Sign up */}
            <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Don&apos;t have an account?{' '}
                <a href="/register" className="hover:underline font-semibold text-white">
                    Sign up for free!
                </a>
            </p>
        </div >
    )
}
