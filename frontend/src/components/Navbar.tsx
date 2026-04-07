'use client'

import { getStoredAccessToken } from '@/lib/auth'
import LogoutButton from '@/components/LogoutButton'
import { AUTHENTICATED_NAV_LINKS, type AppPage, type NavLink } from '@/constants/landing'

interface NavbarProps {
    readonly links: readonly NavLink[]
    readonly brandName?: string
    readonly activePage?: AppPage
}

export default function Navbar({
    links,
    brandName = 'EQUITEK',
    activePage,
}: NavbarProps) {
    const isAuthenticated = Boolean(getStoredAccessToken())
    const visibleLinks = isAuthenticated ? AUTHENTICATED_NAV_LINKS : links

    return (
        <nav
            className="flex items-center justify-between px-8 py-4"
            style={{ backgroundColor: 'var(--brand-primary)' }}
            data-testid="navbar"
        >
            <a
                href="/"
                className="rounded-xl px-2 py-1 text-white font-extrabold text-xl tracking-widest transition-all duration-150 hover:bg-red-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
                {brandName}
            </a>
            <div className="flex gap-6">
                {visibleLinks.map((link) => {
                    const isActive = link.key === activePage

                    return (
                        <a
                            key={link.href}
                            href={link.href}
                            className={`rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-blue-500 ${isActive
                                ? 'bg-white text-red-700 shadow-md'
                                : 'text-white hover:bg-red-600 active:scale-[0.98]'
                                }`}
                        >
                            {link.label}
                        </a>
                    )
                })}
                {isAuthenticated ? <LogoutButton /> : null}
            </div>
        </nav>
    )
}
