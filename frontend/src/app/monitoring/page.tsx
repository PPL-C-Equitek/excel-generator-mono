"use client"

import AuthGuard from '@/components/AuthGuard'
import MonitoringPage from './MonitoringPage'

export default function Page() {
    return (
        <AuthGuard>
            <MonitoringPage />
        </AuthGuard>
    )
}
