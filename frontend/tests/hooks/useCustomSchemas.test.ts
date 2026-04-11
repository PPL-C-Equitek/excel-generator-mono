import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as auth from '../../src/lib/auth'
import { useCustomSchemas } from '../../src/hooks/useCustomSchemas'
import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    ICustomSchemaService,
} from '../../src/lib/ICustomSchemaService'

function createSchemaRecord(overrides: Partial<CustomSchemaRecord> = {}): CustomSchemaRecord {
    return {
        id: '00000000-0000-0000-0000-000000000001',
        owner_id: '11111111-1111-1111-1111-111111111111',
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

function createService(overrides: Partial<ICustomSchemaService> = {}): ICustomSchemaService {
    return {
        list: vi.fn().mockResolvedValue([]),
        create: vi.fn(),
        update: vi.fn(),
        remove: vi.fn().mockResolvedValue(undefined),
        ...overrides,
    }
}

function createDeferred<T>() {
    let resolve!: (value: T | PromiseLike<T>) => void
    let reject!: (reason?: unknown) => void
    const promise = new Promise<T>((nextResolve, nextReject) => {
        resolve = nextResolve
        reject = nextReject
    })

    return {
        promise,
        resolve,
        reject,
    }
}

describe('useCustomSchemas', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('uses stored auth state when the default access token resolver is used', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })
        vi.spyOn(auth, 'getStoredAccessToken').mockReturnValue('stored-access-token')
        vi.spyOn(auth, 'getValidAccessToken').mockResolvedValue('stored-access-token')

        const { result } = renderHook(() => useCustomSchemas(service))

        expect(result.current.hasAccessToken).toBe(true)
        expect(result.current.isLoading).toBe(true)

        await waitFor(() => {
            expect(service.list).toHaveBeenCalledWith('stored-access-token')
        })

        expect(result.current.schemas).toEqual([createSchemaRecord()])
        expect(result.current.isLoading).toBe(false)
    })

    it('loads schemas on mount when an access token is available', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        expect(result.current.hasAccessToken).toBe(true)
        expect(result.current.isLoading).toBe(true)

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(service.list).toHaveBeenCalledWith('access-token')
        expect(result.current.schemas).toEqual([createSchemaRecord()])
        expect(result.current.error).toBeNull()
    })

    it('loads schemas on mount when the access token resolver returns a promise', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })
        const accessTokenResolver = vi.fn().mockResolvedValue('access-token')

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.isLoading).toBe(true)

        await waitFor(() => {
            expect(service.list).toHaveBeenCalledWith('access-token')
        })

        expect(result.current.hasAccessToken).toBe(true)
        expect(result.current.schemas).toEqual([createSchemaRecord()])
    })

    it('stays idle when no access token is available on mount', async () => {
        const service = createService()
        const accessTokenResolver = () => null

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(service.list).not.toHaveBeenCalled()
        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.schemas).toEqual([])
        expect(result.current.error).toBeNull()
    })

    it('clears cached schemas when authentication becomes unavailable after an initial load', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })
        let accessToken: string | null = 'access-token'

        const { result, rerender } = renderHook(
            ({ resolver }) => useCustomSchemas(service, resolver),
            {
                initialProps: {
                    resolver: () => accessToken,
                },
            }
        )

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        accessToken = null

        rerender({
            resolver: () => accessToken,
        })

        await waitFor(() => {
            expect(result.current.hasAccessToken).toBe(false)
        })

        expect(result.current.schemas).toEqual([])
        expect(result.current.error).toBeNull()
    })

    it('stores an initial load error message from Error instances', async () => {
        const service = createService({
            list: vi.fn().mockRejectedValue(new Error('Unable to load schemas.')),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.error).toBe('Unable to load schemas.')
    })

    it('uses the fallback message for non-Error load failures', async () => {
        const service = createService({
            list: vi.fn().mockRejectedValue('load failure'),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.error).toBe('Failed to load custom schemas.')
        })
    })

    it('does not update schemas after a successful load resolves post-unmount', async () => {
        const deferred = createDeferred<CustomSchemaRecord[]>()
        const service = createService({
            list: vi.fn().mockReturnValue(deferred.promise),
        })

        const { unmount } = renderHook(() => useCustomSchemas(service, () => 'access-token'))

        unmount()

        await act(async () => {
            deferred.resolve([createSchemaRecord()])
            await deferred.promise
        })

        expect(service.list).toHaveBeenCalledWith('access-token')
    })

    it('does not update error state after a failed load resolves post-unmount', async () => {
        const deferred = createDeferred<CustomSchemaRecord[]>()
        const service = createService({
            list: vi.fn().mockReturnValue(deferred.promise),
        })

        const { unmount } = renderHook(() => useCustomSchemas(service, () => 'access-token'))

        unmount()

        await act(async () => {
            deferred.reject(new Error('Late load failure.'))
            try {
                await deferred.promise
            } catch {
                // The hook swallows this failure after unmount; the rejection is only for coverage.
            }
        })

        expect(service.list).toHaveBeenCalledWith('access-token')
    })

    it('reloadSchemas clears cached data when the token disappears', async () => {
        let token: string | null = 'access-token'
        const accessTokenResolver = () => token
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        token = null

        await act(async () => {
            await result.current.reloadSchemas()
        })

        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.schemas).toEqual([])
        expect(result.current.error).toBeNull()
        expect(result.current.isLoading).toBe(false)
    })

    it('reloadSchemas keeps the schema list empty when no token is available and no schemas are cached', async () => {
        const service = createService()
        const accessTokenResolver = () => null

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        await act(async () => {
            await result.current.reloadSchemas()
        })

        expect(result.current.schemas).toEqual([])
        expect(result.current.error).toBeNull()
        expect(result.current.isLoading).toBe(false)
    })

    it('reloadSchemas updates schemas after a successful refresh', async () => {
        const service = createService({
            list: vi
                .fn()
                .mockResolvedValueOnce([
                    createSchemaRecord({
                        id: '00000000-0000-0000-0000-000000000002',
                        name: 'B Schema',
                    }),
                ])
                .mockResolvedValueOnce([
                    createSchemaRecord({
                        id: '00000000-0000-0000-0000-000000000003',
                        name: 'A Schema',
                    }),
                ]),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas[0]?.name).toBe('B Schema')
        })

        await act(async () => {
            await result.current.reloadSchemas()
        })

        expect(result.current.schemas[0]?.name).toBe('A Schema')
        expect(service.list).toHaveBeenCalledTimes(2)
    })

    it('reloadSchemas uses the fallback message for non-Error failures', async () => {
        const service = createService({
            list: vi
                .fn()
                .mockResolvedValueOnce([createSchemaRecord()])
                .mockRejectedValueOnce('reload failure'),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        await act(async () => {
            await result.current.reloadSchemas()
        })

        expect(result.current.error).toBe('Failed to load custom schemas.')
    })

    it('reloadSchemas stores the message from Error instances', async () => {
        const service = createService({
            list: vi
                .fn()
                .mockResolvedValueOnce([createSchemaRecord()])
                .mockRejectedValueOnce(new Error('Reload failed.')),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        await act(async () => {
            await result.current.reloadSchemas()
        })

        expect(result.current.error).toBe('Reload failed.')
    })

    it('createSchema rejects when there is no access token', async () => {
        const service = createService()
        const accessTokenResolver = () => null

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasCreated = true
        await act(async () => {
            wasCreated = await result.current.createSchema(createInput)
        })

        expect(wasCreated).toBe(false)
        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.error).toBe('Sign in before saving a custom schema.')
    })

    it('createSchema appends, sorts, and announces a successful save', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord({ name: 'Zulu Mapping' })]),
            create: vi.fn().mockResolvedValue(
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000002',
                    name: 'Alpha Mapping',
                })
            ),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        let wasCreated = false
        await act(async () => {
            wasCreated = await result.current.createSchema(createInput)
        })

        expect(wasCreated).toBe(true)
        expect(result.current.isSaving).toBe(false)
        expect(result.current.schemas.map((schema) => schema.name)).toEqual([
            'Alpha Mapping',
            'Zulu Mapping',
        ])
        expect(result.current.message).toBe('"Alpha Mapping" saved successfully.')
    })

    it('createSchema uses the fallback error for non-Error failures', async () => {
        const service = createService({
            create: vi.fn().mockRejectedValue('save failure'),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasCreated = true
        await act(async () => {
            wasCreated = await result.current.createSchema(createInput)
        })

        expect(wasCreated).toBe(false)
        expect(result.current.error).toBe('Failed to save custom schema.')
        expect(result.current.isSaving).toBe(false)
    })

    it('deleteSchema rejects when there is no access token', async () => {
        const service = createService()
        const accessTokenResolver = () => null

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasDeleted = true
        await act(async () => {
            wasDeleted = await result.current.deleteSchema(
                '00000000-0000-0000-0000-000000000001'
            )
        })

        expect(wasDeleted).toBe(false)
        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.error).toBe('Sign in before deleting a custom schema.')
    })

    it('updateSchema rejects when there is no access token', async () => {
        const service = createService()
        const accessTokenResolver = () => null

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasUpdated = true
        await act(async () => {
            wasUpdated = await result.current.updateSchema(
                '00000000-0000-0000-0000-000000000001',
                createInput
            )
        })

        expect(wasUpdated).toBe(false)
        expect(result.current.hasAccessToken).toBe(false)
        expect(result.current.error).toBe('Sign in before updating a custom schema.')
    })

    it('updateSchema replaces the schema and reports success', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000002',
                    name: 'Zulu Mapping',
                }),
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000001',
                    name: 'Bravo Mapping',
                }),
            ]),
            update: vi.fn().mockResolvedValue(
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000001',
                    name: 'Alpha Mapping',
                })
            ),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(2)
        })

        let wasUpdated = false
        await act(async () => {
            wasUpdated = await result.current.updateSchema(
                '00000000-0000-0000-0000-000000000001',
                createInput
            )
        })

        expect(wasUpdated).toBe(true)
        expect(result.current.isSaving).toBe(false)
        expect(result.current.schemas.map((schema) => schema.name)).toEqual([
            'Alpha Mapping',
            'Zulu Mapping',
        ])
        expect(result.current.message).toBe('"Alpha Mapping" updated successfully.')
    })

    it('updateSchema uses the fallback error for non-Error failures', async () => {
        const service = createService({
            update: vi.fn().mockRejectedValue('update failure'),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasUpdated = true
        await act(async () => {
            wasUpdated = await result.current.updateSchema(
                '00000000-0000-0000-0000-000000000001',
                createInput
            )
        })

        expect(wasUpdated).toBe(false)
        expect(result.current.error).toBe('Failed to update custom schema.')
        expect(result.current.isSaving).toBe(false)
    })

    it('updateSchema stores the message from Error instances', async () => {
        const service = createService({
            update: vi.fn().mockRejectedValue(new Error('Update failed.')),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasUpdated = true
        await act(async () => {
            wasUpdated = await result.current.updateSchema(
                '00000000-0000-0000-0000-000000000001',
                createInput
            )
        })

        expect(wasUpdated).toBe(false)
        expect(result.current.error).toBe('Update failed.')
        expect(result.current.isSaving).toBe(false)
    })

    it('deleteSchema removes the schema and reports success when the name is known', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000007',
                    name: 'Order Mapping',
                }),
            ]),
            remove: vi.fn().mockResolvedValue(undefined),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.schemas).toHaveLength(1)
        })

        let wasDeleted = false
        await act(async () => {
            wasDeleted = await result.current.deleteSchema(
                '00000000-0000-0000-0000-000000000007'
            )
        })

        expect(wasDeleted).toBe(true)
        expect(service.remove).toHaveBeenCalledWith(
            '00000000-0000-0000-0000-000000000007',
            'access-token'
        )
        expect(result.current.schemas).toEqual([])
        expect(result.current.message).toBe('"Order Mapping" deleted successfully.')
        expect(result.current.deletingSchemaId).toBeNull()
    })

    it('deleteSchema succeeds silently when the schema name is missing locally', async () => {
        const service = createService({
            remove: vi.fn().mockResolvedValue(undefined),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasDeleted = false
        await act(async () => {
            wasDeleted = await result.current.deleteSchema(
                '00000000-0000-0000-0000-000000000999'
            )
        })

        expect(wasDeleted).toBe(true)
        expect(result.current.message).toBeNull()
        expect(result.current.schemas).toEqual([])
    })

    it('deleteSchema uses the fallback error for non-Error failures', async () => {
        const service = createService({
            remove: vi.fn().mockRejectedValue('delete failure'),
        })
        const accessTokenResolver = () => 'access-token'

        const { result } = renderHook(() => useCustomSchemas(service, accessTokenResolver))

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        let wasDeleted = true
        await act(async () => {
            wasDeleted = await result.current.deleteSchema(
                '00000000-0000-0000-0000-000000000001'
            )
        })

        expect(wasDeleted).toBe(false)
        expect(result.current.error).toBe('Failed to delete custom schema.')
        expect(result.current.deletingSchemaId).toBeNull()
    })
})
