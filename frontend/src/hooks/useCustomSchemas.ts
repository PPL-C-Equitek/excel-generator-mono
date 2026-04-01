'use client'

import { useEffect, useState } from 'react'
import { getStoredAccessToken } from '@/lib/auth'
import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'

export interface UseCustomSchemasReturn {
    hasAccessToken: boolean
    isLoading: boolean
    isSaving: boolean
    deletingSchemaId: number | null
    schemas: CustomSchemaRecord[]
    error: string | null
    message: string | null
    reloadSchemas: () => Promise<void>
    createSchema: (input: CreateCustomSchemaInput) => Promise<boolean>
    deleteSchema: (schemaId: number) => Promise<boolean>
}

export function useCustomSchemas(
    service: ICustomSchemaService = customSchemaService,
    accessTokenResolver: () => string | null = getStoredAccessToken
): UseCustomSchemasReturn {
    const initialAccessToken = accessTokenResolver()
    const [hasAccessToken, setHasAccessToken] = useState(
        typeof initialAccessToken === 'string' && initialAccessToken.length > 0
    )
    const [isLoading, setIsLoading] = useState(
        typeof initialAccessToken === 'string' && initialAccessToken.length > 0
    )
    const [isSaving, setIsSaving] = useState(false)
    const [deletingSchemaId, setDeletingSchemaId] = useState<number | null>(null)
    const [schemas, setSchemas] = useState<CustomSchemaRecord[]>([])
    const [error, setError] = useState<string | null>(null)
    const [message, setMessage] = useState<string | null>(null)

    useEffect(() => {
        let isCancelled = false

        const load = async () => {
            const accessToken = accessTokenResolver()
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
    }, [accessTokenResolver, service])

    const reloadSchemas = async () => {
        const accessToken = accessTokenResolver()
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
        const accessToken = accessTokenResolver()

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
            setSchemas((prev) => [...prev, createdSchema].sort((left, right) => left.name.localeCompare(right.name)))
            setMessage(`"${createdSchema.name}" saved successfully.`)
            return true
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to save custom schema.')
            return false
        } finally {
            setIsSaving(false)
        }
    }

    const deleteSchema = async (schemaId: number): Promise<boolean> => {
        const accessToken = accessTokenResolver()

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
        deleteSchema,
    }
}
