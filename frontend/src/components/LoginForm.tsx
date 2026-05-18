'use client'

import useLoginForm from '@/hooks/useLoginForm'

export interface LoginFormData {
    email: string
    password: string
}

interface LoginFormProps {
    onSubmit?: (data: LoginFormData) => void
    onGoogleSignIn?: () => void
    isLoading?: boolean
    apiError?: string | null
    onClearApiError?: () => void
}

export default function LoginForm({ onSubmit, onGoogleSignIn, isLoading = false, apiError = null, onClearApiError }: Readonly<LoginFormProps>) {
    const {
        email,
        setEmail,
        password,
        setPassword,
        error: validationError,
        handleSubmit,
    } = useLoginForm({
        onSubmit: ({ email, password }) => onSubmit?.({ email, password }),
    })

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
                    onChange={(e) => { setEmail(e.target.value); onClearApiError?.(); }}
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-60 disabled:cursor-not-allowed"
                    style={{
                        backgroundColor: 'var(--surface-2)',
                        color: 'var(--foreground)',
                    }}
                    disabled={isLoading}
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
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); onClearApiError?.(); }}
                    className="w-full px-4 py-3 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-60 disabled:cursor-not-allowed"
                    style={{
                        backgroundColor: 'var(--surface-2)',
                        color: 'var(--foreground)',
                    }}
                    disabled={isLoading}
                />
            </div>

            {/* Error - below password */}
            {(validationError || apiError) && (
                <div
                    role="alert"
                    className="mb-4 rounded-lg border p-3 text-sm"
                    style={{
                        backgroundColor: 'var(--danger-bg)',
                        borderColor: 'var(--danger-border)',
                        color: 'var(--danger-text)',
                    }}
                >
                    {validationError || apiError}
                </div>
            )}

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
                disabled={isLoading}
                className="w-full py-3 rounded-xl font-bold text-sm mb-3 transition active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-600"
                style={{ backgroundColor: '#ffffff', color: 'var(--brand-primary)' }}
            >
                {isLoading ? 'Signing In...' : 'Sign In'}
            </button>

            {/* Sign in with Google */}
            <button
                type="button"
                onClick={() => onGoogleSignIn?.()}
                disabled={isLoading}
                className="w-full py-3 rounded-xl font-bold text-sm mb-6 flex items-center justify-center gap-2 transition active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-600"
                style={{ backgroundColor: '#ffffff', color: '#111827' }}
            >
                <span className="text-base">G</span>{' '}
                {isLoading ? 'Signing In...' : 'Sign In with Google'}
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
