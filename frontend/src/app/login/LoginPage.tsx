'use client'
import Navbar from '@/components/Navbar'
import LoginForm from '@/components/LoginForm'
import { LANDING_NAV_LINKS } from '@/constants/landing'
import useLoginForm from '@/hooks/useLoginForm'

export default function LoginPage() {
    const {
        error,
        success,
        isLoading,
        handleLogin,
        triggerGoogleSignIn,
        dismissError,
        dismissSuccess,
    } = useLoginForm()

    return (
        <div className="force-light min-h-screen flex flex-col bg-gray-50">
            <Navbar links={LANDING_NAV_LINKS} activePage="login" />
            <main className="flex flex-1 items-center justify-center px-4 py-12">
                <LoginForm
                    onSubmit={handleLogin}
                    onGoogleSignIn={triggerGoogleSignIn}
                    errorMessage={error}
                    onDismissError={dismissError}
                    successMessage={success}
                    onDismissSuccess={dismissSuccess}
                    isLoading={isLoading}
                />
            </main>
        </div>
    )
}
