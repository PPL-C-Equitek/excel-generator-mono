import type {
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

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function readStringField(data: unknown, field: string): string | null {
    if (!isRecord(data)) {
        return null
    }

    const value = data[field]
    return typeof value === 'string' ? value : null
}

function findFirstString(values: unknown[]): string | null {
    const firstString = values.find((value) => typeof value === 'string')
    return typeof firstString === 'string' ? firstString : null
}

function readNestedString(data: unknown): string | null {
    if (!isRecord(data)) {
        return null
    }

    for (const value of Object.values(data)) {
        if (typeof value === 'string') {
            return value
        }

        if (Array.isArray(value)) {
            const nestedString = findFirstString(value)
            if (nestedString) {
                return nestedString
            }
        }
    }

    return null
}

function readErrorMessage(data: unknown, fallback: string): string {
    return (
        readStringField(data, 'message') ??
        readStringField(data, 'detail') ??
        (Array.isArray(data) ? findFirstString(data) : null) ??
        readNestedString(data) ??
        fallback
    )
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
