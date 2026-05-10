'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getMonitoringAccess } from '@/services/monitoring'

type MonitoringRoleGuardProps = Readonly<{
    children: ReactNode
    redirectTo?: string
    loadingFallback?: ReactNode
}>

export default function MonitoringRoleGuard({
    children,
    redirectTo = '/convert',
    loadingFallback = null,
}: MonitoringRoleGuardProps) {
    const router = useRouter()
    const [isChecking, setIsChecking] = useState(true)
    const [isAuthorized, setIsAuthorized] = useState(false)

    useEffect(() => {
        let isCancelled = false

        const verifyMonitoringAccess = async () => {
            setIsChecking(true)

            try {
                const accessDecision = await getMonitoringAccess()

                if (isCancelled) {
                    return
                }

                if (!accessDecision.allowed) {
                    setIsAuthorized(false)
                    router.replace(redirectTo)
                    return
                }

                setIsAuthorized(true)
                setIsChecking(false)
            } catch {
                if (!isCancelled) {
                    setIsAuthorized(false)
                    router.replace(redirectTo)
                }
            }
        }

        void verifyMonitoringAccess()

        return () => {
            isCancelled = true
        }
    }, [redirectTo, router])

    if (isChecking || !isAuthorized) {
        return <>{loadingFallback}</>
    }

    return <>{children}</>
}
