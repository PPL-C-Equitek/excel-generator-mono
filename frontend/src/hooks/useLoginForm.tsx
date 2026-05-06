import { useEffect, useRef, useState } from 'react'
import { useGoogleLogin } from '@react-oauth/google'
import { login, loginWithGoogle } from '@/lib/api'
import { storeAuthTokens } from '@/lib/auth'
import type { LoginFormData } from '@/components/LoginForm'

interface AuthenticatedUser {
    name: string
    email: string
}

function persistUser(user?: AuthenticatedUser): void {
    if (!user || globalThis.localStorage === undefined) {
        return
    }

    globalThis.localStorage.setItem('user_name', user.name)
    globalThis.localStorage.setItem('user_email', user.email)
}

export default function useLoginForm() {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const redirectTimeoutRef = useRef<ReturnType<typeof globalThis.setTimeout> | null>(null)

    useEffect(() => {
        return () => {
            if (redirectTimeoutRef.current) {
                globalThis.clearTimeout(redirectTimeoutRef.current)
            }
        }
    }, [])

    const saveTokensAndRedirect = (
        accessToken: string,
        refreshToken: string,
        user?: AuthenticatedUser
    ) => {
        storeAuthTokens(accessToken, refreshToken)
        persistUser(user)

        redirectTimeoutRef.current = globalThis.setTimeout(() => {
            globalThis.location.href = '/convert'
        }, 2000)
    }

    const beginLoginAttempt = () => {
        setIsLoading(true)
        setError(null)
        setSuccess(null)
    }

    const failLoginAttempt = (nextError: unknown, fallbackMessage: string) => {
        setIsLoading(false)

        if (nextError instanceof Error) {
            setError(nextError.message || fallbackMessage)
            return
        }

        setError('Something went wrong')
    }

    const handleLogin = async (data: LoginFormData) => {
        try {
            beginLoginAttempt()

            const response = await login(data.email, data.password)
            setSuccess(`Welcome back! You're being redirected to your workspace...`)
            saveTokensAndRedirect(response.access_token, response.refresh_token, response.user)
        } catch (nextError: unknown) {
            failLoginAttempt(nextError, 'Login failed. Please try again.')
        }
    }

    const googleSignIn = useGoogleLogin({
        onSuccess: async (tokenResponse) => {
            try {
                beginLoginAttempt()

                const response = await loginWithGoogle(tokenResponse.access_token)
                setSuccess(`Welcome! You're being redirected to your workspace...`)
                saveTokensAndRedirect(response.access_token, response.refresh_token, response.user)
            } catch (nextError: unknown) {
                failLoginAttempt(nextError, 'Google sign-in failed.')
            }
        },
        onError: () => {
            setError('Google sign-in cancelled or failed')
        },
        scope: 'openid email profile',
    })

    const triggerGoogleSignIn = () => {
        if (!googleClientId) {
            setError('Google OAuth belum dikonfigurasi. Isi NEXT_PUBLIC_GOOGLE_CLIENT_ID lalu restart frontend.')
            return
        }

        googleSignIn()
    }

    return {
        error,
        success,
        isLoading,
        handleLogin,
        triggerGoogleSignIn,
        dismissError: () => setError(null),
        dismissSuccess: () => setSuccess(null),
    }
}
