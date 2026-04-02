'use client'
import Navbar from '@/components/Navbar'
import LoginForm from '@/components/LoginForm'
import { LANDING_NAV_LINKS } from '@/constants/landing'
import type { LoginFormData } from '@/components/LoginForm'
import { login } from '@/lib/api'

export default function LoginPage() {
    const handleLogin = async (data: LoginFormData) => {
        try {
            const res = await login(data.email, data.password)

            localStorage.setItem('access_token', res.access_token)
            localStorage.setItem('refresh_token', res.refresh_token)

            window.location.href = '/convert'
        } catch (err: unknown) {
            if (err instanceof Error) {
                alert(err.message)
            } else {
                alert('Something went wrong')
            }
        }
    }

    return (
        <div className="force-light min-h-screen flex flex-col">
            <Navbar links={LANDING_NAV_LINKS} activePage="login" />
            <main className="flex flex-1 items-center justify-center px-4 py-12">
                <LoginForm onSubmit={handleLogin} />
            </main>
        </div>
    )
}