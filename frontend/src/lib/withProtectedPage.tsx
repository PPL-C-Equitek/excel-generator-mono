'use client'

import { useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { hasValidSession } from '@/lib/auth'

type ProtectedPageOptions = {
    redirectTo?: string
    loadingFallback?: ReactNode
}

export function withProtectedPage<P extends object>(
    WrappedComponent: ComponentType<P>,
    options: ProtectedPageOptions = {}
) {
    const { redirectTo = '/login', loadingFallback = null } = options

    function ProtectedPage(props: P) {
        const router = useRouter()
        const [isCheckingAuth, setIsCheckingAuth] = useState(true)

        useEffect(() => {
            let isCancelled = false

            const checkAuth = async () => {
                const isSessionValid = await hasValidSession()

                if (isCancelled) {
                    return
                }

                if (!isSessionValid) {
                    router.replace(redirectTo)
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
            return <>{loadingFallback}</>
        }

        return <WrappedComponent {...props} />
    }

    ProtectedPage.displayName = `withProtectedPage(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`

    return ProtectedPage
}
