import { useState } from 'react'
import { getLoginValidationError } from '@/lib/loginValidation'

export interface LoginFormData {
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

        const validationError = getLoginValidationError({ email, password })
        if (validationError) {
            setError(validationError)
            return
        }

        options?.onSubmit?.({ email, password, rememberMe })
    }

    return { email, setEmail, password, setPassword, rememberMe, setRememberMe, error, handleSubmit }
}
