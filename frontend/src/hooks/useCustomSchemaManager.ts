'use client'

import type { ComponentPropsWithoutRef } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useCustomSchemas } from '@/hooks/useCustomSchemas'
import { getValidAccessToken } from '@/lib/auth'
import type {
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'
import {
    CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE,
    isCustomSchemaLimitExceededErrorMessage,
    MAX_CUSTOM_SCHEMAS,
    createEmptyColumn,
    createEmptyDraft,
    buildDraftFromSchema,
    buildCustomSchemaInput,
    getNextColumnsAfterRemoval,
    getTrimmedDraftColumns,
    validateCustomSchemaDraft,
    type CustomSchemaFormDraft,
} from '@/lib/customSchemaDraft'

type AccessTokenResolver = () => string | null | Promise<string | null>
type FormSubmitEvent = Parameters<
    NonNullable<ComponentPropsWithoutRef<'form'>['onSubmit']>
>[0]

interface UseCustomSchemaManagerProps {
    readonly service?: ICustomSchemaService
    readonly accessTokenResolver?: AccessTokenResolver
}

export interface UseCustomSchemaManagerReturn {
    readonly draft: CustomSchemaFormDraft
    readonly isModalOpen: boolean
    readonly isDeleteDialogOpen: boolean
    readonly schemaPendingDeletion: CustomSchemaRecord | null
    readonly formError: string | null
    readonly hasAccessToken: boolean
    readonly isLoading: boolean
    readonly isSaving: boolean
    readonly deletingSchemaId: string | null
    readonly schemas: CustomSchemaRecord[]
    readonly message: string | null
    readonly error: string | null
    readonly isAtLimit: boolean
    readonly isAddDisabled: boolean
    readonly modalTitle: string
    readonly modalDescription: string
    readonly saveButtonLabel: string
    readonly shouldShowPageError: string | null
    readonly reloadSchemas: () => Promise<void>
    readonly openCreateModal: () => void
    readonly openEditModal: (schema: CustomSchemaRecord) => void
    readonly openDeleteDialog: (schema: CustomSchemaRecord) => void
    readonly closeSchemaModal: () => void
    readonly closeDeleteDialog: () => void
    readonly handleColumnChange: (
        columnId: number,
        field: 'name' | 'description',
        value: string
    ) => void
    readonly handleAddColumn: () => void
    readonly handleRemoveColumn: (columnId: number) => void
    readonly handleSubmit: (event: FormSubmitEvent) => Promise<void>
    readonly handleConfirmDelete: (schema: CustomSchemaRecord) => Promise<void>
    readonly setDraftName: (value: string) => void
    readonly setDraftDescription: (value: string) => void
    readonly trimDraftDescription: () => void
    readonly trimDraftColumnName: (columnId: number) => void
    readonly trimDraftColumnDescription: (columnId: number) => void
    readonly clearFormError: () => void
}

function mapFormSubmitEventToFunction(
    event: Readonly<{ preventDefault: () => void }>
): void {
    event.preventDefault()
}

export function useCustomSchemaManager(
    {
        service = customSchemaService,
        accessTokenResolver = getValidAccessToken,
    }: UseCustomSchemaManagerProps = {}
): UseCustomSchemaManagerReturn {
    const [draft, setDraft] = useState<CustomSchemaFormDraft>(createEmptyDraft)
    const [formError, setFormError] = useState<string | null>(null)
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [editingSchemaId, setEditingSchemaId] = useState<string | null>(null)
    const [schemaPendingDeletion, setSchemaPendingDeletion] =
        useState<CustomSchemaRecord | null>(null)
    const nextColumnIdRef = useRef(2)

    const {
        hasAccessToken,
        isLoading,
        isSaving,
        deletingSchemaId,
        schemas,
        error,
        message,
        saveError,
        reloadSchemas,
        createSchema,
        updateSchema,
        deleteSchema,
        clearSaveError,
    } = useCustomSchemas(service, accessTokenResolver)

    const isAtLimit = schemas.length >= MAX_CUSTOM_SCHEMAS
    const isAddDisabled = !hasAccessToken || isLoading || isSaving || isAtLimit

    const resetDraft = useCallback(() => {
        nextColumnIdRef.current = 2
        setDraft(createEmptyDraft())
        setEditingSchemaId(null)
        setFormError(null)
    }, [])

    const openCreateModal = useCallback(() => {
        resetDraft()
        clearSaveError()
        setIsModalOpen(true)
    }, [clearSaveError, resetDraft])

    const openEditModal = (schema: CustomSchemaRecord): void => {
        if (hasAccessToken && !isLoading && !isSaving) {
            const nextDraft = buildDraftFromSchema(schema)
            nextColumnIdRef.current = nextDraft.columns.length + 1
            setDraft(nextDraft)
            setEditingSchemaId(schema.id)
            setFormError(null)
            clearSaveError()
            setIsModalOpen(true)
        }
    }

    const openDeleteDialog = (schema: CustomSchemaRecord): void => {
        setSchemaPendingDeletion(schema)
    }

    const closeSchemaModal = useCallback(() => {
        if (isSaving) {
            return
        }

        setIsModalOpen(false)
        resetDraft()
    }, [isSaving, resetDraft])

    const closeDeleteDialog = useCallback(() => {
        if (deletingSchemaId) {
            return
        }

        setSchemaPendingDeletion(null)
    }, [deletingSchemaId])

    useEffect(() => {
        if (!isModalOpen || !saveError) {
            return
        }

        // eslint-disable-next-line react-hooks/set-state-in-effect
        setFormError(saveError)
    }, [isModalOpen, saveError])

    useEffect(() => {
        if (!isModalOpen) {
            return
        }

        const handleKeyDown = (event: globalThis.KeyboardEvent) => {
            if (event.key === 'Escape') {
                closeSchemaModal()
            }
        }

        globalThis.addEventListener('keydown', handleKeyDown)

        return () => {
            globalThis.removeEventListener('keydown', handleKeyDown)
        }
    }, [isModalOpen, closeSchemaModal])

    useEffect(() => {
        if (!schemaPendingDeletion) {
            return
        }

        const handleKeyDown = (event: globalThis.KeyboardEvent) => {
            if (event.key === 'Escape') {
                closeDeleteDialog()
            }
        }

        globalThis.addEventListener('keydown', handleKeyDown)

        return () => {
            globalThis.removeEventListener('keydown', handleKeyDown)
        }
    }, [schemaPendingDeletion, closeDeleteDialog])

    const handleColumnChange = (
        columnId: number,
        field: 'name' | 'description',
        value: string
    ): void => {
        setFormError(null)
        setDraft((prev) => ({
            ...prev,
            columns: prev.columns.map((column) =>
                column.id === columnId ? { ...column, [field]: value } : column
            ),
        }))
    }

    const handleAddColumn = (): void => {
        setFormError(null)
        setDraft((prev) => ({
            ...prev,
            columns: [...prev.columns, createEmptyColumn(nextColumnIdRef.current++)],
        }))
    }

    const handleRemoveColumn = (columnId: number): void => {
        setFormError(null)
        setDraft((prev) => ({
            ...prev,
            columns: getNextColumnsAfterRemoval(prev.columns, columnId),
        }))
    }

    const handleSubmit = async (event: FormSubmitEvent): Promise<void> => {
        mapFormSubmitEventToFunction(event)

        const normalizedDraft = getTrimmedDraftColumns({
            ...draft,
            name: draft.name.trim(),
            description: draft.description.trim(),
        })

        const validationError = validateCustomSchemaDraft(normalizedDraft)
        if (validationError) {
            setFormError(validationError)
            return
        }

        setFormError(null)
        const schemaInput = buildCustomSchemaInput(normalizedDraft)

        const wasSaved = editingSchemaId
            ? await updateSchema(editingSchemaId, schemaInput)
            : await createSchema(schemaInput)

        if (wasSaved) {
            closeSchemaModal()
        }
    }

    const handleConfirmDelete = async (schema: CustomSchemaRecord): Promise<void> => {
        const wasDeleted = await deleteSchema(schema.id)
        if (wasDeleted) {
            setSchemaPendingDeletion(null)
        }
    }

    const setDraftName = useCallback((value: string) => {
        setFormError(null)
        setDraft((prev) => ({ ...prev, name: value }))
    }, [])

    const setDraftDescription = useCallback((value: string) => {
        setFormError(null)
        setDraft((prev) => ({ ...prev, description: value }))
    }, [])

    const trimDraftDescription = useCallback(() => {
        setDraft((prev) => ({
            ...prev,
            description: prev.description.trim(),
        }))
    }, [])

    const trimDraftColumnName = useCallback((columnId: number) => {
        setDraft((prev) => ({
            ...prev,
            columns: prev.columns.map((column) =>
                column.id === columnId ? { ...column, name: column.name.trim() } : column
            ),
        }))
    }, [])

    const trimDraftColumnDescription = useCallback((columnId: number) => {
        setDraft((prev) => ({
            ...prev,
            columns: prev.columns.map((column) =>
                column.id === columnId
                    ? { ...column, description: column.description.trim() }
                    : column
            ),
        }))
    }, [])

    const clearFormError = useCallback(() => {
        setFormError(null)
    }, [])

    const modalTitle = editingSchemaId ? 'Edit Schema' : 'Add Schema'
    const modalDescription = editingSchemaId
        ? 'Update the saved output columns for this schema.'
        : 'Define the output columns you want to reuse later.'

    let saveButtonLabel = 'Save schema'
    if (isSaving) {
        saveButtonLabel = 'Saving...'
    } else if (editingSchemaId) {
        saveButtonLabel = 'Save changes'
    }

    const shouldShowPageError =
        error !== null &&
        error !== CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE &&
        !isCustomSchemaLimitExceededErrorMessage(error)
            ? error
            : null

    return {
        draft,
        isModalOpen,
        isDeleteDialogOpen: schemaPendingDeletion !== null,
        schemaPendingDeletion,
        formError,
        hasAccessToken,
        isLoading,
        isSaving,
        deletingSchemaId,
        schemas,
        message,
        error,
        isAtLimit,
        isAddDisabled,
        modalTitle,
        modalDescription,
        saveButtonLabel,
        shouldShowPageError,
        reloadSchemas,
        openCreateModal,
        openEditModal,
        openDeleteDialog,
        closeSchemaModal,
        closeDeleteDialog,
        handleColumnChange,
        handleAddColumn,
        handleRemoveColumn,
        handleSubmit,
        handleConfirmDelete,
        setDraftName,
        setDraftDescription,
        trimDraftDescription,
        trimDraftColumnName,
        trimDraftColumnDescription,
        clearFormError,
    }
}

export type { SchemaColumnDraft } from '@/lib/customSchemaDraft'
