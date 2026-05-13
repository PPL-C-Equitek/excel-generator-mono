import { useEffect, useRef, useState } from 'react'
import { useGoogleLogin } from '@react-oauth/google'
import { login, loginWithGoogle } from '@/lib/api'
import { storeAuthTokens } from '@/lib/auth'
import type { LoginFormData } from '@/components/LoginForm'

interface AuthenticatedUser {
    name: string
    email: string
}

const EMAIL_REGEX = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+$/

function persistUser(user?: AuthenticatedUser): void {
    if (!user || globalThis.localStorage === undefined) {
        return
    }

    globalThis.localStorage.setItem('user_name', user.name)
    globalThis.localStorage.setItem('user_email', user.email)
}

export default function useLoginForm() {
    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
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

    const validateForm = (): LoginFormData | null => {
        if (!email || email.length > 254 || !EMAIL_REGEX.test(email)) {
            setError('Please enter a valid email address.')
            return null
        }

        if (!password.trim()) {
            setError('Password is required.')
            return null
        }

        return { email, password }
    }

    const handleLogin = async () => {
        const formData = validateForm()
        if (!formData) {
            return
        }

        try {
            beginLoginAttempt()

            const response = await login(formData.email, formData.password)
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
        email,
        password,
        error,
        success,
        isLoading,
        isFormDisabled: isLoading || !!success,
        handleLogin,
        triggerGoogleSignIn,
        handleEmailChange: (value: string) => {
            setEmail(value)
        },
        handlePasswordChange: (value: string) => {
            setPassword(value)
        },
        dismissError: () => setError(null),
        dismissSuccess: () => setSuccess(null),
    }
}
