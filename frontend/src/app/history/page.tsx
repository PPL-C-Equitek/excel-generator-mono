"use client"

import AuthGuard from '@/components/AuthGuard'
import HistoryPage from './HistoryPage'

export default function Page() {
    return (
        <AuthGuard>
            <HistoryPage />
        </AuthGuard>
    )
}
