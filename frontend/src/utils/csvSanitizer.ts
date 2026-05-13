/**
 * Mencegah CSV Injection vulnerability.
 * Jika string dimulai dengan karakter berbahaya (=, +, -, @),
 * tambahkan karakter quote (') di depannya agar spreadsheet program
 * membacanya sebagai teks alih-alih mengeksekusi rumus macro.
 * 
 * Fungsi ini melakukan deep copy sederhana dan murni non-mutating.
 */
function shouldEscapeCSVFormulaCell(value: string): boolean {
    return /^\s*[=+\-@]/.test(value)
}

function sanitizeObject(obj: Record<string, unknown>): Record<string, unknown> {
    const newObj: Record<string, unknown> = {}
    for (const key of Object.keys(obj)) {
        newObj[key] = sanitizeCSVCell(obj[key])
    }
    return newObj
}

export function sanitizeCSVCell(data: unknown): unknown {
    if (typeof data === 'string') {
        if (shouldEscapeCSVFormulaCell(data)) {
            return "'" + data
        }
    } else if (Array.isArray(data)) {
        return data.map(sanitizeCSVCell)
    } else if (data !== null && typeof data === 'object') {
        return sanitizeObject(data as Record<string, unknown>)
    }
    return data
}
