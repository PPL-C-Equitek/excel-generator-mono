"use client"

import ConvertPage from './ConvertPage'
import AuthGuard from '@/components/AuthGuard'

export default function Page() {
    return (
        <AuthGuard>
            <ConvertPage />
        </AuthGuard>
    )
}
