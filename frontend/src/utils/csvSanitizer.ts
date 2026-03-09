/**
 * Mencegah CSV Injection vulnerability.
 * Jika string dimulai dengan karakter berbahaya (=, +, -, @),
 * tambahkan karakter quote (') di depannya agar spreadsheet program
 * membacanya sebagai teks alih-alih mengeksekusi rumus macro.
 * 
 * Fungsi ini melakukan deep copy sederhana dan murni non-muting.
 */
export function sanitizeCSVCell(data: unknown): unknown {
    if (typeof data === 'string') {
        if (/^[=+\-@]/.test(data)) {
            return "'" + data
        }
    } else if (Array.isArray(data)) {
        return data.map(sanitizeCSVCell)
    } else if (data !== null && typeof data === 'object') {
        const obj = data as Record<string, unknown>
        const newObj: Record<string, unknown> = {}
        for (const key in obj) {
            newObj[key] = sanitizeCSVCell(obj[key])
        }
        return newObj
    }
    return data
}
