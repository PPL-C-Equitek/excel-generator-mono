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
                className="w-full rounded-xl bg-white px-4 py-2 text-sm font-semibold text-red-700 shadow-md transition-all duration-150 hover:bg-red-50 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {isLoading ? 'Logging out...' : 'Logout'}
            </button>

            {message ? (
                <p
                    role="status"
                    aria-live="polite"
                    className="mt-2 rounded-lg border border-red-400 bg-red-50 px-3 py-2 text-sm text-red-700"
                >
                    {message}
                </p>
            ) : null}
        </div>
    )
}
