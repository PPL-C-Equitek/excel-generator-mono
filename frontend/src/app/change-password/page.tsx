import AuthGuard from '@/components/AuthGuard'
import ChangePasswordPage from './ChangePasswordPage'

export default function Page() {
    return (
        <AuthGuard>
            <ChangePasswordPage />
        </AuthGuard>
    )
}
