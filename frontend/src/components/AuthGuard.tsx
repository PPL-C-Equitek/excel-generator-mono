'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { hasValidSession } from '@/lib/auth'

type AuthGuardProps = {
    children: ReactNode
    redirectTo?: string
    loadingFallback?: ReactNode
}

export default function AuthGuard({
    children,
    redirectTo = '/login',
    loadingFallback = null,
}: Readonly<AuthGuardProps>) {
    const router = useRouter()
    const pathname = usePathname()
    const [isChecking, setIsChecking] = useState(true)
    const [isAuthorized, setIsAuthorized] = useState(false)

    useEffect(() => {
        let isCancelled = false

        const verifyAccess = async () => {
            setIsChecking(true)

            const isSessionValid = await hasValidSession()

            if (isCancelled) {
                return
            }

            if (!isSessionValid) {
                setIsAuthorized(false)
                router.replace(redirectTo)
                return
            }

            setIsAuthorized(true)
            setIsChecking(false)
        }

        const revalidateAccess = () => {
            void verifyAccess()
        }

        void verifyAccess()
        globalThis.addEventListener('popstate', revalidateAccess)
        globalThis.addEventListener('pageshow', revalidateAccess)

        return () => {
            isCancelled = true
            globalThis.removeEventListener('popstate', revalidateAccess)
            globalThis.removeEventListener('pageshow', revalidateAccess)
        }
    }, [pathname, redirectTo, router])

    if (isChecking || !isAuthorized) {
        return <>{loadingFallback}</>
    }

    return <>{children}</>
}
