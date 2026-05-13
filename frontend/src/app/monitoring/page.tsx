"use client"

import AuthGuard from '@/components/AuthGuard'
import MonitoringRoleGuard from '@/components/MonitoringRoleGuard'
import MonitoringPage from './MonitoringPage'

export default function Page() {
    return (
        <AuthGuard>
            <MonitoringRoleGuard>
                <MonitoringPage />
            </MonitoringRoleGuard>
        </AuthGuard>
    )
}
