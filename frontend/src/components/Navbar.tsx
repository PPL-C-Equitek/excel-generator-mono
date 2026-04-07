import type { NavLink } from '@/constants/landing'

type Page = 'login' | 'register'

interface NavbarProps {
    readonly links: readonly NavLink[]
    readonly brandName?: string
    readonly activePage?: Page
}

export default function Navbar({
    links,
    brandName = 'EQUITEK',
    activePage,
}: NavbarProps) {
    return (
        <nav
            className="flex items-center justify-between px-8 py-4"
            style={{ backgroundColor: 'var(--brand-primary)' }}
            data-testid="navbar"
        >
            <span className="text-white font-extrabold text-xl tracking-widest">
                {brandName}
            </span>
            <div className="flex gap-6">
                {links.map((link) => {
                    const isActive = link.key === activePage

                    return (
                        <a
                            key={link.href}
                            href={link.href}
                            className={`text-sm font-medium transition ${isActive
                                ? 'text-white font-bold underline'
                                : 'text-white hover:underline'
                                }`}
                        >
                            {link.label}
                        </a>
                    )
                })}
            </div>
        </nav>
    )
}