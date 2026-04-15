'use client'
import Navbar from '@/components/Navbar'
import LoginForm from '@/components/LoginForm'
import { LANDING_NAV_LINKS } from '@/constants/landing'
import type { LoginFormData } from '@/components/LoginForm'
import { useGoogleLogin } from '@react-oauth/google'
import { login, loginWithGoogle } from '@/lib/api'
import { storeAuthTokens } from '@/lib/auth'
import { useState } from 'react'

export default function LoginPage() {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
    const [error, setError] = useState<string | null>(null)

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

        globalThis.location.href = '/convert'
    }

    const handleLogin = async (data: LoginFormData) => {
        try {
            const res = await login(data.email, data.password)
            saveTokensAndRedirect(res.access_token, res.refresh_token, res.user)
        } catch (err: unknown) {
            if (err instanceof Error) {
                setError(err.message || 'Login failed. Please try again.')
            } else {
                setError('Something went wrong')
            }
        }
    }

    const triggerGoogleSignIn = useGoogleLogin({
        onSuccess: async (tokenResponse) => {
            try {
                const res = await loginWithGoogle(tokenResponse.access_token)
                saveTokensAndRedirect(res.access_token, res.refresh_token, res.user)
            } catch (err: unknown) {
                if (err instanceof Error) {
                    setError(err.message || 'Google sign-in failed.')
                } else {
                    setError('Something went wrong')
                }
            }
        },
        onError: () => {
            setError('Google sign-in cancelled or failed')
        },
        scope: 'openid email profile',
    })

    return (
        <div className="force-light min-h-screen flex flex-col bg-gray-50">
            <Navbar links={LANDING_NAV_LINKS} activePage="login" />
            <main className="flex flex-1 items-center justify-center px-4 py-12">
                <LoginForm
                    onSubmit={handleLogin}
                    onGoogleSignIn={() => {
                        if (!googleClientId) {
                            setError('Google OAuth belum dikonfigurasi. Isi NEXT_PUBLIC_GOOGLE_CLIENT_ID lalu restart frontend.')
                            return
                        }

                        triggerGoogleSignIn()
                    }}
                    errorMessage={error}
                    onDismissError={() => setError(null)}
                />
            </main>
        </div>
    )
}
