import AuthGuard from '@/components/AuthGuard'
import SchemaPage from './SchemaPage'

export default function Page() {
    return (
        <AuthGuard>
            <SchemaPage />
        </AuthGuard>
    )
}
