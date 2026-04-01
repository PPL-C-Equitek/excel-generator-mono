import Navbar from '@/components/Navbar'
import LoginForm from '@/components/LoginForm'
import { LANDING_NAV_LINKS } from '@/constants/landing'

export default function LoginPage() {
    return (
        <div
            className="force-light min-h-screen flex flex-col"
            style={{ backgroundColor: 'var(--surface-1)', colorScheme: 'light' }}
        >
            <Navbar links={LANDING_NAV_LINKS} activePage="login" />
            <main className="flex flex-1 items-center justify-center px-4 py-12">
                <LoginForm />
            </main>
        </div>
    )
}