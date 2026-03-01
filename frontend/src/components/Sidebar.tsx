interface SidebarProps {
    activeMenu: 'convert' | 'history'
    username: string
    onLogout?: () => void
}

export default function Sidebar({ activeMenu, username, onLogout }: SidebarProps) {
    const menus = [
        { key: 'convert', label: 'Convert', href: '/convert' },
        { key: 'history', label: 'History', href: '/history' },
    ]

    return (
        <aside className="w-56 min-h-screen bg-red-700 flex flex-col">
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