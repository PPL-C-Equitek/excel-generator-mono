import type { NavLink } from '@/constants/landing'

interface NavbarProps {
    readonly links: readonly NavLink[]
    readonly brandName?: string
}

export default function Navbar({
    links,
    brandName = 'EQUITEK',
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
                {links.map((link) => (
                    <a
                        key={link.href}
                        href={link.href}
                        className="text-white text-sm font-medium hover:underline transition"
                    >
                        {link.label}
                    </a>
                ))}
            </div>
        </nav>
    )
}