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
        return shouldEscapeCSVFormulaCell(data) ? "'" + data : data
    }
    
    if (Array.isArray(data)) {
        return data.map(sanitizeCSVCell)
    }
    
    if (data !== null && typeof data === 'object') {
        return sanitizeObject(data as Record<string, unknown>)
    }
    
    return data
}
