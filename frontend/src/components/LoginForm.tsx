'use client'

export interface LoginFormData {
    email: string
    password: string
}

interface LoginFormProps {
    email: string
    password: string
    onEmailChange: (value: string) => void
    onPasswordChange: (value: string) => void
    onSubmit: () => void
    onGoogleSignIn: () => void
    errorMessage?: string | null
    onDismissError?: () => void
    successMessage?: string | null
    onDismissSuccess?: () => void
    isLoading?: boolean
    isDisabled?: boolean
}

export default function LoginForm({
    email,
    password,
    onEmailChange,
    onPasswordChange,
    onSubmit,
    onGoogleSignIn,
    errorMessage,
    onDismissError,
    successMessage,
    onDismissSuccess,
    isLoading = false,
    isDisabled = false,
}: Readonly<LoginFormProps>) {
    return (
        <div
            className="rounded-2xl p-10 w-full max-w-lg mx-auto"
            style={{ backgroundColor: 'var(--brand-primary)' }}
        >
            <h1 className="text-white font-bold text-2xl text-center mb-1">Login</h1>
            <p className="text-center text-sm mb-6" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Sign in to continue to your workspace.
            </p>

            {errorMessage && (
                <div
                    role="alert"
                    className="mb-4 flex items-start justify-between gap-3 rounded-lg border p-3 text-sm"
                    style={{
                        backgroundColor: 'var(--danger-bg)',
                        borderColor: 'var(--danger-border)',
                        color: 'var(--danger-text)',
                    }}
                >
                    <span>{errorMessage}</span>
                    {onDismissError ? (
                        <button
                            type="button"
                            onClick={onDismissError}
                            aria-label="Dismiss error"
                            className="shrink-0"
                        >
                            ×
                        </button>
                    ) : null}
                </div>
            )}

            {successMessage && (
                <output
                    className="mb-4 flex items-start justify-between gap-3 rounded-lg border p-3 text-sm"
                    style={{
                        backgroundColor: 'var(--success-bg)',
                        borderColor: 'var(--success-border)',
                        color: 'var(--success-text)',
                    }}
                >
                    <span>{successMessage}</span>
                    {onDismissSuccess ? (
                        <button
                            type="button"
                            onClick={onDismissSuccess}
                            aria-label="Dismiss success"
                            className="shrink-0"
                        >
                            ×
                        </button>
                    ) : null}
                </output>
            )}

            <form
                onSubmit={(event) => {
                    event.preventDefault()
                    onSubmit()
                }}
            >
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
                        onChange={(event) => onEmailChange(event.target.value)}
                        disabled={isDisabled}
                        className="w-full px-4 py-3 rounded-xl text-sm outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                            backgroundColor: 'var(--surface-2)',
                            color: 'var(--foreground)',
                        }}
                    />
                </div>

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
                        onChange={(event) => onPasswordChange(event.target.value)}
                        disabled={isDisabled}
                        className="w-full px-4 py-3 rounded-xl text-sm outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                            backgroundColor: 'var(--surface-2)',
                            color: 'var(--foreground)',
                        }}
                    />
                </div>

                <div className="flex items-center justify-between mb-6">
                    <a
                        href="/forgot-password"
                        className="text-white font-bold text-sm hover:underline"
                    >
                        Forgot Password?
                    </a>
                </div>

                <button
                    type="submit"
                    disabled={isDisabled}
                    className="w-full py-3 rounded-xl font-bold text-sm mb-3 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ backgroundColor: '#ffffff', color: 'var(--brand-primary)' }}
                >
                    {isLoading ? 'Signing in...' : 'Sign In'}
                </button>

                <button
                    type="button"
                    onClick={onGoogleSignIn}
                    disabled={isDisabled}
                    className="w-full py-3 rounded-xl font-bold text-sm mb-6 flex items-center justify-center gap-2 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ backgroundColor: '#ffffff', color: '#111827' }}
                >
                    <span className="text-base">G</span>{' '}
                    {isLoading ? 'Signing in...' : 'Sign In with Google'}
                </button>

                <p className="text-center text-sm" style={{ color: 'rgba(255,255,255,0.75)' }}>
                    Don&apos;t have an account?{' '}
                    <a href="/register" className="hover:underline font-semibold text-white">
                        Sign up for free!
                    </a>
                </p>
            </form>
        </div >
    )
}
