import { useState } from 'react'

interface LoginFormData {
    email: string
    password: string
    rememberMe: boolean
}

interface UseLoginFormOptions {
    onSubmit?: (data: LoginFormData) => void
}

export default function useLoginForm(options?: UseLoginFormOptions) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [rememberMe, setRememberMe] = useState(false)
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
        if (!email || !emailRegex.test(email)) {
            setError('Please enter a valid email address.')
            return
        }

        // Validasi password
        if (!password) {
            setError('Password is required.')
            return
        }
        options?.onSubmit?.({ email, password, rememberMe })
    }

    return { email, setEmail, password, setPassword, rememberMe, setRememberMe, error, handleSubmit }
}