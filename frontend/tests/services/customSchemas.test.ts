import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
} from '@/lib/ICustomSchemaService'

function createSchemaRecord(overrides: Partial<CustomSchemaRecord> = {}): CustomSchemaRecord {
    return {
        id: 1,
        owner_id: '11111111-1111-1111-1111-111111111111',
        name: 'Invoice Mapping',
        description: 'Maps invoice rows',
        version: 1,
        is_active: false,
        definition: {
            columns: [
                {
                    name: 'invoice_number',
                    description: 'Invoice identifier',
                },
            ],
        },
        prompt_fragment: 'Prompt fragment',
        created_at: '2026-04-01T10:00:00Z',
        updated_at: '2026-04-01T10:00:00Z',
        ...overrides,
    }
}

const createInput: CreateCustomSchemaInput = {
    name: 'Invoice Mapping',
    description: 'Maps invoice rows',
    is_active: false,
    definition: {
        columns: [
            {
                name: 'invoice_number',
                description: 'Invoice identifier',
            },
        ],
    },
}

async function importFreshService(apiUrl?: string) {
    vi.resetModules()

    if (apiUrl === undefined) {
        vi.unstubAllEnvs()
    } else {
        vi.stubEnv('NEXT_PUBLIC_API_URL', apiUrl)
    }

    return import('@/services/customSchemas')
}

describe('customSchemaService', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
        vi.unstubAllEnvs()
    })

    it('lists schemas with the default API URL and bearer auth header', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => [createSchemaRecord()],
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()
        const result = await customSchemaService.list('access-token')

        expect(result).toEqual([createSchemaRecord()])
        expect(mockedFetch).toHaveBeenCalledTimes(1)
        expect(mockedFetch.mock.calls[0][0]).toBe('http://localhost:8000/schemas/')

        const options = mockedFetch.mock.calls[0][1] as RequestInit
        expect((options.headers as Headers).get('Authorization')).toBe('Bearer access-token')
    })

    it('strips a trailing slash from NEXT_PUBLIC_API_URL for create requests', async () => {
        const createdSchema = createSchemaRecord({ id: 7, name: 'Receipt Mapping' })
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 201,
            json: async () => createdSchema,
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService('http://localhost:9999/')
        const result = await customSchemaService.create(createInput, 'access-token')

        expect(result).toEqual(createdSchema)
        expect(mockedFetch.mock.calls[0][0]).toBe('http://localhost:9999/schemas/')

        const options = mockedFetch.mock.calls[0][1] as RequestInit
        expect(options.method).toBe('POST')
        expect(options.body).toBe(JSON.stringify(createInput))
        expect((options.headers as Headers).get('Authorization')).toBe('Bearer access-token')
        expect((options.headers as Headers).get('Content-Type')).toBe('application/json')
    })

    it('does not overwrite an existing content type header when the Headers implementation already reports one', async () => {
        const nativeHeaders = globalThis.Headers

        class FakeHeaders {
            private readonly values = new Map<string, string>()

            constructor() {}

            set(name: string, value: string) {
                this.values.set(name.toLowerCase(), value)
            }

            has(name: string) {
                return name.toLowerCase() === 'content-type'
            }

            get(name: string) {
                return this.values.get(name.toLowerCase()) ?? null
            }
        }

        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 201,
            json: async () => createSchemaRecord(),
        })

        vi.stubGlobal('Headers', FakeHeaders as unknown as typeof Headers)
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()
        await customSchemaService.create(createInput, 'access-token')

        const options = mockedFetch.mock.calls[0][1] as RequestInit
        expect((options.headers as FakeHeaders).get('Authorization')).toBe('Bearer access-token')
        expect((options.headers as FakeHeaders).get('Content-Type')).toBeNull()

        vi.stubGlobal('Headers', nativeHeaders)
    })

    it('returns undefined for a 204 delete response', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 204,
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()
        const result = await customSchemaService.remove(42, 'access-token')

        expect(result).toBeUndefined()
        expect(mockedFetch.mock.calls[0][0]).toBe('http://localhost:8000/schemas/42/')

        const options = mockedFetch.mock.calls[0][1] as RequestInit
        expect(options.method).toBe('DELETE')
    })

    it('prefers the message field when the API returns an error payload', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ message: 'Schema limit reached.' }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow(
            'Schema limit reached.'
        )
    })

    it('falls back to the detail field when message is absent', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ detail: 'Unauthorized.' }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow('Unauthorized.')
    })

    it('reads the first string from an array error payload', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ['First schema error', 'Second schema error'],
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow(
            'First schema error'
        )
    })

    it('reads the first string value from an object error payload', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ name: 'Schema name is invalid.' }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow(
            'Schema name is invalid.'
        )
    })

    it('reads the first string inside an object array value', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({ definition: ['Column names must be unique.'] }),
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow(
            'Column names must be unique.'
        )
    })

    it('falls back to the default error when the response body cannot be parsed', async () => {
        const mockedFetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => {
                throw new Error('invalid json')
            },
        })
        vi.stubGlobal('fetch', mockedFetch)

        const { customSchemaService } = await importFreshService()

        await expect(customSchemaService.list('access-token')).rejects.toThrow(
            'Request failed. Please try again.'
        )
    })
})
