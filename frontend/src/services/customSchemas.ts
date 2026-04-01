import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
    .split('')
    .reduceRight((acc, ch) => (acc === '' && ch === '/' ? acc : ch + acc), '')

function buildApiUrl(path: string): string {
    const normalizedPath = path.replace(/^\/+/, '')
    return `${API_URL}/${normalizedPath}`
}

function readErrorMessage(data: unknown, fallback: string): string {
    if (
        typeof data === 'object' &&
        data !== null &&
        'message' in data &&
        typeof (data as { message: unknown }).message === 'string'
    ) {
        return (data as { message: string }).message
    }

    if (
        typeof data === 'object' &&
        data !== null &&
        'detail' in data &&
        typeof (data as { detail: unknown }).detail === 'string'
    ) {
        return (data as { detail: string }).detail
    }

    if (Array.isArray(data)) {
        const firstString = data.find((item) => typeof item === 'string')
        if (typeof firstString === 'string') {
            return firstString
        }
    }

    if (typeof data === 'object' && data !== null) {
        for (const value of Object.values(data as Record<string, unknown>)) {
            if (typeof value === 'string') {
                return value
            }

            if (Array.isArray(value)) {
                const firstString = value.find((item) => typeof item === 'string')
                if (typeof firstString === 'string') {
                    return firstString
                }
            }
        }
    }

    return fallback
}

async function requestCustomSchemaApi<T>(
    path: string,
    accessToken: string,
    options?: RequestInit
): Promise<T> {
    const headers = new Headers(options?.headers)
    headers.set('Authorization', `Bearer ${accessToken}`)

    if (options?.body && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json')
    }

    const response = await fetch(buildApiUrl(path), {
        ...options,
        headers,
    })

    if (response.status === 204) {
        return undefined as T
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
        throw new Error(readErrorMessage(data, 'Request failed. Please try again.'))
    }

    return data as T
}

export const customSchemaService: ICustomSchemaService = {
    list(accessToken) {
        return requestCustomSchemaApi<CustomSchemaRecord[]>('schemas/', accessToken)
    },
    create(input, accessToken) {
        return requestCustomSchemaApi<CustomSchemaRecord>('schemas/', accessToken, {
            method: 'POST',
            body: JSON.stringify(input),
        })
    },
    remove(schemaId, accessToken) {
        return requestCustomSchemaApi<void>(`schemas/${schemaId}/`, accessToken, {
            method: 'DELETE',
        })
    },
}
