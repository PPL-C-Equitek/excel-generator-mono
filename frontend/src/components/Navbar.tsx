const NAV_LINKS = [
    { label: 'Login', href: '/login' },
    { label: 'Register', href: '/register' },
]

export default function Navbar() {
    return (
        <nav
            className="flex items-center justify-between px-8 py-4"
            style={{ backgroundColor: 'var(--brand-primary)' }}
        >
            <span className="text-white font-extrabold text-xl tracking-widest">
                EQUITEK
            </span>
            <div className="flex gap-6">
                {NAV_LINKS.map((link) => (
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