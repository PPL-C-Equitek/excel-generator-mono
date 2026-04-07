'use client'

import { useCallback, useEffect, useState } from 'react'
import { getValidAccessToken, getStoredAccessToken } from '@/lib/auth'
import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'

type AccessTokenResolver = () => string | null | Promise<string | null>

export interface UseCustomSchemasReturn {
    hasAccessToken: boolean
    isLoading: boolean
    isSaving: boolean
    deletingSchemaId: string | null
    schemas: CustomSchemaRecord[]
    error: string | null
    message: string | null
    reloadSchemas: () => Promise<void>
    createSchema: (input: CreateCustomSchemaInput) => Promise<boolean>
    updateSchema: (schemaId: string, input: CreateCustomSchemaInput) => Promise<boolean>
    deleteSchema: (schemaId: string) => Promise<boolean>
}

interface InitialAuthState {
    hasAccessToken: boolean
    isLoading: boolean
}

function sortSchemas(schemas: CustomSchemaRecord[]): CustomSchemaRecord[] {
    return [...schemas].sort((left, right) => left.name.localeCompare(right.name))
}

function getInitialAuthState(
    accessTokenResolver: AccessTokenResolver
): InitialAuthState {
    if (accessTokenResolver === getValidAccessToken) {
        const initialAccessToken = getStoredAccessToken()
        const authenticated = !!initialAccessToken
        return {
            hasAccessToken: authenticated,
            isLoading: authenticated,
        }
    }

    const initialAccessToken = accessTokenResolver()
    if (typeof initialAccessToken === 'string') {
        const authenticated = initialAccessToken.length > 0
        return {
            hasAccessToken: authenticated,
            isLoading: authenticated,
        }
    }

    return {
        hasAccessToken: false,
        isLoading: initialAccessToken instanceof Promise,
    }
}

export function useCustomSchemas(
    service: ICustomSchemaService = customSchemaService,
    accessTokenResolver: AccessTokenResolver = getValidAccessToken
): UseCustomSchemasReturn {
    const [initialAuthState] = useState(() =>
        getInitialAuthState(accessTokenResolver)
    )
    const [hasAccessToken, setHasAccessToken] = useState(
        initialAuthState.hasAccessToken
    )
    const [isLoading, setIsLoading] = useState(initialAuthState.isLoading)
    const [isSaving, setIsSaving] = useState(false)
    const [deletingSchemaId, setDeletingSchemaId] = useState<string | null>(null)
    const [schemas, setSchemas] = useState<CustomSchemaRecord[]>([])
    const [error, setError] = useState<string | null>(null)
    const [message, setMessage] = useState<string | null>(null)

    const resolveAccessToken = useCallback(async (): Promise<string | null> => {
        const value = accessTokenResolver()
        return value instanceof Promise ? await value : value
    }, [accessTokenResolver])

    useEffect(() => {
        let isCancelled = false

        const load = async () => {
            const accessToken = await resolveAccessToken()
            const authenticated = typeof accessToken === 'string' && accessToken.length > 0

            setHasAccessToken(authenticated)
            setMessage(null)

            if (!authenticated) {
                setSchemas((prev) => (prev.length === 0 ? prev : []))
                setError(null)
                setIsLoading(false)
                return
            }

            setIsLoading(true)
            setError(null)

            try {
                const nextSchemas = await service.list(accessToken)
                if (!isCancelled) {
                    setSchemas(nextSchemas)
                }
            } catch (err: unknown) {
                if (!isCancelled) {
                    setError(err instanceof Error ? err.message : 'Failed to load custom schemas.')
                }
            } finally {
                if (!isCancelled) {
                    setIsLoading(false)
                }
            }
        }

        void load()

        return () => {
            isCancelled = true
        }
    }, [resolveAccessToken, service])

    const reloadSchemas = async () => {
        const accessToken = await resolveAccessToken()
        const authenticated = typeof accessToken === 'string' && accessToken.length > 0

        setHasAccessToken(authenticated)
        setMessage(null)

        if (!authenticated) {
            setSchemas((prev) => (prev.length === 0 ? prev : []))
            setError(null)
            setIsLoading(false)
            return
        }

        setIsLoading(true)
        setError(null)

        try {
            const nextSchemas = await service.list(accessToken)
            setSchemas(nextSchemas)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load custom schemas.')
        } finally {
            setIsLoading(false)
        }
    }

    const createSchema = async (input: CreateCustomSchemaInput): Promise<boolean> => {
        const accessToken = await resolveAccessToken()

        if (!accessToken) {
            setHasAccessToken(false)
            setError('Sign in before saving a custom schema.')
            return false
        }

        setHasAccessToken(true)
        setIsSaving(true)
        setError(null)
        setMessage(null)

        try {
            const createdSchema = await service.create(input, accessToken)
            setSchemas((prev) => sortSchemas([...prev, createdSchema]))
            setMessage(`"${createdSchema.name}" saved successfully.`)
            return true
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to save custom schema.')
            return false
        } finally {
            setIsSaving(false)
        }
    }

    const updateSchema = async (
        schemaId: string,
        input: CreateCustomSchemaInput
    ): Promise<boolean> => {
        const accessToken = await resolveAccessToken()

        if (!accessToken) {
            setHasAccessToken(false)
            setError('Sign in before updating a custom schema.')
            return false
        }

        setHasAccessToken(true)
        setIsSaving(true)
        setError(null)
        setMessage(null)

        try {
            const updatedSchema = await service.update(schemaId, input, accessToken)
            setSchemas((prev) =>
                sortSchemas(
                    prev.map((schema) =>
                        schema.id === schemaId ? updatedSchema : schema
                    )
                )
            )
            setMessage(`"${updatedSchema.name}" updated successfully.`)
            return true
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to update custom schema.')
            return false
        } finally {
            setIsSaving(false)
        }
    }

    const deleteSchema = async (schemaId: string): Promise<boolean> => {
        const accessToken = await resolveAccessToken()

        if (!accessToken) {
            setHasAccessToken(false)
            setError('Sign in before deleting a custom schema.')
            return false
        }

        setHasAccessToken(true)
        setDeletingSchemaId(schemaId)
        setError(null)
        setMessage(null)

        const schemaName = schemas.find((schema) => schema.id === schemaId)?.name

        try {
            await service.remove(schemaId, accessToken)
            setSchemas((prev) => prev.filter((schema) => schema.id !== schemaId))
            if (schemaName) {
                setMessage(`"${schemaName}" deleted successfully.`)
            }
            return true
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to delete custom schema.')
            return false
        } finally {
            setDeletingSchemaId(null)
        }
    }

    return {
        hasAccessToken,
        isLoading,
        isSaving,
        deletingSchemaId,
        schemas,
        error,
        message,
        reloadSchemas,
        createSchema,
        updateSchema,
        deleteSchema,
    }
}
