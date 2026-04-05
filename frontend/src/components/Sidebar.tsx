'use client'

import { useEffect, useState } from "react"
import { getStoredUser } from "@/lib/auth"
interface SidebarProps {
    readonly activeMenu: 'convert' | 'schema' | 'history'
    readonly onLogout?: () => void
}

export default function Sidebar({ activeMenu, onLogout }: SidebarProps) {
    const menus = [
        { key: 'convert', label: 'Convert', href: '/convert' },
        { key: 'schema', label: 'Schema', href: '/schema' },
        { key: 'history', label: 'History', href: '/history' },
    ]

    const [username, setUsername] = useState<string>("User")

    useEffect(() => {
        const user = getStoredUser()
        if (user) setUsername(user.name)
    }, [])

    return (
        <aside className="fixed inset-y-0 left-0 w-56 overflow-y-auto bg-red-700 flex flex-col">
            <div className="px-6 py-5">
                <h1 className="text-white font-extrabold text-xl tracking-widest">EQUITEK</h1>
            </div>

            <nav className="flex flex-col gap-1 px-3">
                {menus.map((menu) => (
                    <a
                        key={menu.key}
                        href={menu.href}
                        className={`px-4 py-2 rounded font-semibold text-sm transition
              ${activeMenu === menu.key
                                ? 'bg-white text-red-700'
                                : 'text-white hover:bg-red-600'}`}
                    >
                        {menu.label}
                    </a>
                ))}
            </nav>

            <div className="mt-auto px-4 py-4 flex items-center gap-2">
                <span className="text-white font-bold text-sm">{username}</span>
                <button onClick={onLogout} className="text-white hover:text-gray-200 ml-1">→</button>
            </div>
        </aside>
    )
}
