"use client"

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import ConvertPage from './ConvertPage'
import { getValidAccessToken } from '@/lib/auth'

// Debug function
// function parseJwt(token: string) {
//     try {
//         const base64Payload = token.split('.')[1]
//         const payload = atob(base64Payload)
//         return JSON.parse(payload)
//     } catch {
//         return null
//     }
// }

export default function Page() {
    const router = useRouter()
    const [isCheckingAuth, setIsCheckingAuth] = useState(true)

    useEffect(() => {
        let isCancelled = false

        const checkAuth = async () => {
            const accessToken = await getValidAccessToken()

            if (isCancelled) {
                return
            }

            if (!accessToken) {
                router.replace('/login')
                return
            }

            setIsCheckingAuth(false)
        }

        void checkAuth()

        return () => {
            isCancelled = true
        }
    }, [router])

    if (isCheckingAuth) {
        return null
    }

    return <ConvertPage />
}