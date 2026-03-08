export default function Navbar() {
    return (
        <nav className="bg-red-700 px-8 py-4 flex items-center justify-between">
            <span className="text-white font-extrabold text-xl tracking-wide">
                EQUITEK
            </span>
            <div className="flex gap-6">
                <a href="/login" className="text-white text-sm font-medium hover:underline">
                    Login
                </a>
                <a href="/register" className="text-white text-sm font-medium hover:underline">
                    Register
                </a>
            </div>
        </nav>
    )
}