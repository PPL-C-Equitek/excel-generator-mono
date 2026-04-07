'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { clearAuthTokens } from '@/lib/auth'

function clearCookie(name: string) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
}

export default function LogoutButton() {
    const router = useRouter()
    const [isLoading, setIsLoading] = useState(false)
    const [message, setMessage] = useState('')

    const handleLogout = async () => {
        if (isLoading) {
            return
        }

        setIsLoading(true)

        try {
            await fetch('/auth/logout/', {
                method: 'POST',
            })
        } finally {
            clearAuthTokens()
            clearCookie('access_token')
            clearCookie('refresh_token')
            clearCookie('accessToken')
            clearCookie('refreshToken')
            setMessage('Berhasil keluar')
            router.push('/')
            setIsLoading(false)
        }
    }

    return (
        <div>
            <button
                type="button"
                onClick={handleLogout}
                disabled={isLoading}
                aria-label="Logout"
            >
                {isLoading ? 'Logging out...' : 'Logout'}
            </button>

            {message ? (
                <p role="status" aria-live="polite">
                    {message}
                </p>
            ) : null}
        </div>
    )
}
