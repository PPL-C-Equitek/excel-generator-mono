'use client'

import { useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getValidAccessToken } from '@/lib/auth'

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
                const accessToken = await getValidAccessToken()

                if (isCancelled) {
                    return
                }

                if (!accessToken) {
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
