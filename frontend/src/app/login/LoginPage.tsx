'use client'
import { useState } from 'react'
import Navbar from '@/components/Navbar'
import LoginForm from '@/components/LoginForm'
import { LANDING_NAV_LINKS } from '@/constants/landing'
import type { LoginFormData } from '@/components/LoginForm'
import { useGoogleLogin } from '@react-oauth/google'
import { login, loginWithGoogle } from '@/lib/api'
import { storeAuthTokens } from '@/lib/auth'

export default function LoginPage() {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
    const [isLoading, setIsLoading] = useState(false)
    const [apiError, setApiError] = useState<string | null>(null)
    const [showSuccessMessage, setShowSuccessMessage] = useState(false)

    const saveTokensAndRedirect = (
        accessToken: string,
        refreshToken: string,
        user?: { name: string; email: string }
    ) => {
        storeAuthTokens(accessToken, refreshToken)

        if (user) {
            localStorage.setItem('user_name', user.name)
            localStorage.setItem('user_email', user.email)
        }

        setShowSuccessMessage(true)
        setTimeout(() => {
            globalThis.location.href = '/convert'
        }, 2000)
    }

    const handleLogin = async (data: LoginFormData) => {
        try {
            setIsLoading(true)
            setApiError(null)
            const res = await login(data.email, data.password)
            saveTokensAndRedirect(res.access_token, res.refresh_token, res.user)
        } catch (err: unknown) {
            setIsLoading(false)
            if (err instanceof Error) {
                setApiError(err.message)
            } else {
                setApiError('Something went wrong. Please try again.')
            }
        }
    }

    const triggerGoogleSignIn = useGoogleLogin({
        onSuccess: async (tokenResponse) => {
            try {
                setIsLoading(true)
                setApiError(null)
                const res = await loginWithGoogle(tokenResponse.access_token)
                saveTokensAndRedirect(res.access_token, res.refresh_token, res.user)
            } catch (err: unknown) {
                setIsLoading(false)
                if (err instanceof Error) {
                    setApiError(err.message)
                } else {
                    setApiError('Google sign-in failed. Please try again.')
                }
            }
        },
        onError: () => {
            setApiError('Google sign-in cancelled or failed. Please try again.')
        },
        scope: 'openid email profile',
    })

    return (
        <div className="force-light min-h-screen flex flex-col bg-gray-50">
            <Navbar links={LANDING_NAV_LINKS} activePage="login" />
            <main className="flex flex-1 items-center justify-center px-4 py-12">
                {/* Success Message */}
                {showSuccessMessage && (
                    <div className="fixed top-4 left-4 right-4 mx-auto max-w-lg rounded-lg border border-green-200 bg-green-50 p-4 text-sm font-medium text-green-800 shadow-lg z-50 flex items-center gap-3">
                        <svg
                            className="h-5 w-5 flex-shrink-0 text-green-600"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth="2"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z"
                            />
                        </svg>
                        <span>Login successful! Redirecting...</span>
                    </div>
                )}

                <LoginForm
                    onSubmit={handleLogin}
                    onGoogleSignIn={() => {
                        if (!googleClientId) {
                            setApiError('Google OAuth belum dikonfigurasi. Isi NEXT_PUBLIC_GOOGLE_CLIENT_ID lalu restart frontend.')
                            return
                        }

                        triggerGoogleSignIn()
                    }}
                    isLoading={isLoading}
                    apiError={apiError}
                    onClearApiError={() => setApiError(null)}
                />
            </main>
        </div>
    )
}
