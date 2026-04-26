'use client'

import Link from 'next/link'
import { useState } from "react"
import { getStoredUser } from "@/lib/auth"
import LogoutButton from "@/components/LogoutButton"
import HistorySidebarList from "@/components/HistorySidebarList"
interface SidebarProps {
    readonly activeMenu: 'home' | 'convert' | 'schema' | 'history' | 'monitoring' | 'change-password'
    readonly onLogout?: () => void
    readonly selectedHistoryId?: string | null
}

export default function Sidebar({ activeMenu, onLogout, selectedHistoryId }: SidebarProps) {
    const menus = [
        { key: 'convert', label: 'Convert', href: '/convert' },
        { key: 'schema', label: 'Schema', href: '/schema' },
        { key: 'history', label: 'History', href: '/history' },
        { key: 'monitoring', label: 'Monitoring', href: '/monitoring' },
        { key: 'change-password', label: 'Change Password', href: '/change-password' },
    ]

    const [username] = useState<string>(() => {
        return getStoredUser()?.name ?? 'User'
    })

    return (
        <aside className="fixed inset-y-0 left-0 w-56 overflow-y-auto bg-red-700 flex flex-col">
            <div className="px-6 py-5">
                <Link
                    href="/"
                    className="inline-flex rounded-xl px-2 py-1 text-white font-extrabold text-xl tracking-widest transition-all duration-150 hover:bg-red-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    EQUITEK
                </Link>
            </div>

            <nav className="flex flex-col gap-1 px-3">
                {menus.map((menu) => (
                    <a
                        key={menu.key}
                        href={menu.href}
                        className={`px-4 py-2 rounded font-semibold text-base transition
              ${activeMenu === menu.key
                                ? 'bg-white text-red-700'
                                : 'text-white hover:bg-red-600'}`}
                    >
                        {menu.label}
                    </a>
                ))}
            </nav>

            <div className="mt-3 flex min-h-0 flex-1 flex-col border-t border-white/20 px-3 pt-3">
                <HistorySidebarList selectedHistoryId={selectedHistoryId} />
            </div>

            <div className="mt-auto border-t border-white/20 px-4 py-4">
                <div className="mb-3 flex min-w-0 items-center gap-3">
                    <span
                        title={username}
                        className="min-w-0 flex-1 truncate text-white font-bold text-sm"
                    >
                        {username}
                    </span>
                </div>
                {onLogout ? (
                    <button
                        type="button"
                        onClick={onLogout}
                        aria-label="Logout"
                        className="w-full rounded-xl bg-white px-4 py-2 text-sm font-semibold text-red-700 shadow-md transition-all duration-150 hover:bg-red-50 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        Logout
                    </button>
                ) : (
                    <div className="w-full">
                        <LogoutButton />
                    </div>
                )}
            </div>
        </aside>
    )
}
