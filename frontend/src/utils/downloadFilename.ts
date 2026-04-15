const UTF8_FILENAME_PREFIX = /^UTF-8''/i

function sanitizeDownloadFilename(candidate: string | null | undefined): string | null {
    if (typeof candidate !== 'string') {
        return null
    }

    const normalized = candidate
        .trim()
        .replace(/\r/g, '')
        .replace(/\n/g, '')
        .replace(/\x00/g, '')
        .replace(/^"(.*)"$/, '$1')

    if (!normalized) {
        return null
    }

    const basename = normalized.split(/[\\/]/).pop()?.trim()
    if (!basename || basename === '.' || basename === '..') {
        return null
    }

    return basename
}

function decodeHeaderFilename(value: string): string {
    const normalized = value.trim().replace(UTF8_FILENAME_PREFIX, '')

    try {
        return decodeURIComponent(normalized)
    } catch {
        return normalized
    }
}

export function resolveDownloadFilename(headers: Headers, fallback: string): string {
    const contentDisposition = headers.get('Content-Disposition')
    if (!contentDisposition) {
        return fallback
    }

    const encodedFilenameMatch = contentDisposition.match(/filename\*\s*=\s*([^;]+)/i)
    if (encodedFilenameMatch) {
        const encodedFilename = sanitizeDownloadFilename(
            decodeHeaderFilename(encodedFilenameMatch[1])
        )
        if (encodedFilename) {
            return encodedFilename
        }
    }

    const quotedFilenameMatch = contentDisposition.match(/filename\s*=\s*"([^"]+)"/i)
    if (quotedFilenameMatch) {
        const quotedFilename = sanitizeDownloadFilename(quotedFilenameMatch[1])
        if (quotedFilename) {
            return quotedFilename
        }
    }

    const plainFilenameMatch = contentDisposition.match(/filename\s*=\s*([^;]+)/i)
    if (plainFilenameMatch) {
        const plainFilename = sanitizeDownloadFilename(plainFilenameMatch[1])
        if (plainFilename) {
            return plainFilename
        }
    }

    return fallback
}
