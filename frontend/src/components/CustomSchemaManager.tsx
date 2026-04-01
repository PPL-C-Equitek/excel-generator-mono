'use client'

import type { FormEvent, KeyboardEvent, MouseEvent } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useCustomSchemas } from '@/hooks/useCustomSchemas'
import { getStoredAccessToken } from '@/lib/auth'
import type {
    CreateCustomSchemaInput,
    CustomSchemaDefinition,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'

interface CustomSchemaManagerProps {
    readonly service?: ICustomSchemaService
    readonly accessTokenResolver?: () => string | null
}

interface SchemaColumnDraft {
    id: number
    name: string
    description: string
}

interface CustomSchemaFormDraft {
    name: string
    description: string
    columns: SchemaColumnDraft[]
}

const MAX_CUSTOM_SCHEMAS = 5

function createEmptyColumn(id: number): SchemaColumnDraft {
    return {
        id,
        name: '',
        description: '',
    }
}

function createEmptyDraft(): CustomSchemaFormDraft {
    return {
        name: '',
        description: '',
        columns: [createEmptyColumn(1)],
    }
}

export function validateCustomSchemaDraft(draft: CustomSchemaFormDraft): string | null {
    if (!draft.name.trim()) {
        return 'Schema name is required.'
    }

    if (draft.columns.length === 0) {
        return 'Add at least one column.'
    }

    const seenColumnNames = new Set<string>()

    for (let index = 0; index < draft.columns.length; index += 1) {
        const column = draft.columns[index]
        const columnName = column.name.trim()
        const columnDescription = column.description.trim()

        if (!columnName) {
            return `Column ${index + 1} name is required.`
        }

        if (!columnDescription) {
            return `Column ${index + 1} description is required.`
        }

        const normalizedName = columnName.toLowerCase()
        if (seenColumnNames.has(normalizedName)) {
            return 'Column names must be unique.'
        }

        seenColumnNames.add(normalizedName)
    }

    return null
}

export function buildCustomSchemaInput(
    draft: CustomSchemaFormDraft
): CreateCustomSchemaInput {
    const definition: CustomSchemaDefinition = {
        columns: draft.columns.map((column) => ({
            name: column.name.trim(),
            description: column.description.trim(),
        })),
    }

    return {
        name: draft.name.trim(),
        description: draft.description.trim(),
        is_active: false,
        definition,
    }
}

export default function CustomSchemaManager({
    service = customSchemaService,
    accessTokenResolver = getStoredAccessToken,
}: CustomSchemaManagerProps) {
    const [draft, setDraft] = useState<CustomSchemaFormDraft>(createEmptyDraft)
    const [formError, setFormError] = useState<string | null>(null)
    const [isModalOpen, setIsModalOpen] = useState(false)
    const nextColumnIdRef = useRef(2)
    const {
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
    } = useCustomSchemas(service, accessTokenResolver)

    const isAtLimit = schemas.length >= MAX_CUSTOM_SCHEMAS
    const isAddDisabled = !hasAccessToken || isLoading || isSaving || isAtLimit

    const resetDraft = useCallback(() => {
        nextColumnIdRef.current = 2
        setDraft(createEmptyDraft())
        setFormError(null)
    }, [])

    const openCreateModal = () => {
        if (isAddDisabled) {
            return
        }

        resetDraft()
        setIsModalOpen(true)
    }

    const closeCreateModal = useCallback(() => {
        if (isSaving) {
            return
        }

        setIsModalOpen(false)
        resetDraft()
    }, [isSaving, resetDraft])

    useEffect(() => {
        if (!isModalOpen) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                closeCreateModal()
            }
        }

        window.addEventListener('keydown', handleKeyDown)

        return () => {
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [isModalOpen, closeCreateModal])

    const handleColumnChange = (
        columnId: number,
        field: 'name' | 'description',
        value: string
    ) => {
        setFormError(null)
        setDraft((prev) => ({
            ...prev,
            columns: prev.columns.map((column) =>
                column.id === columnId ? { ...column, [field]: value } : column
            ),
        }))
    }

    const handleAddColumn = () => {
        setFormError(null)
        setDraft((prev) => ({
            ...prev,
            columns: [...prev.columns, createEmptyColumn(nextColumnIdRef.current++)],
        }))
    }

    const handleRemoveColumn = (columnId: number) => {
        setFormError(null)
        setDraft((prev) => {
            if (prev.columns.length === 1) {
                return prev
            }

            return {
                ...prev,
                columns: prev.columns.filter((column) => column.id !== columnId),
            }
        })
    }

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()

        const validationError = validateCustomSchemaDraft(draft)
        if (validationError) {
            setFormError(validationError)
            return
        }

        setFormError(null)
        const wasCreated = await createSchema(buildCustomSchemaInput(draft))
        if (wasCreated) {
            closeCreateModal()
        }
    }

    const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
        if (event.target === event.currentTarget) {
            closeCreateModal()
        }
    }

    const handleBackdropKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.target !== event.currentTarget) {
            return
        }

        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            closeCreateModal()
        }
    }

    return (
        <>
            <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900">Saved Schemas</h2>
                        <p className="mt-1 text-sm text-gray-500">
                            Manage reusable output mappings for future conversions.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        <span
                            data-testid="schema-count"
                            className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700"
                        >
                            {schemas.length}/{MAX_CUSTOM_SCHEMAS} saved
                        </span>
                        {hasAccessToken && (
                            <button
                                type="button"
                                onClick={() => {
                                    void reloadSchemas()
                                }}
                                disabled={isLoading}
                                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                Refresh
                            </button>
                        )}
                        <button
                            data-testid="add-schema-btn"
                            type="button"
                            onClick={openCreateModal}
                            disabled={isAddDisabled}
                            className="rounded-xl bg-red-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            Add schema
                        </button>
                    </div>
                </div>

                {message && (
                    <div
                        data-testid="schema-message"
                        className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700"
                    >
                        {message}
                    </div>
                )}

                {(error || isAtLimit) && (
                    <div
                        data-testid="schema-error"
                        className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                    >
                        {error || `You have reached the ${MAX_CUSTOM_SCHEMAS}-schema limit.`}
                    </div>
                )}

                {hasAccessToken && isLoading ? (
                    <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
                        Loading your saved schemas...
                    </div>
                ) : null}

                {hasAccessToken && !isLoading && schemas.length === 0 ? (
                    <div className="mt-6 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center">
                        <h3 className="text-base font-semibold text-gray-900">
                            No saved schemas yet
                        </h3>
                        <p className="mt-2 text-sm text-gray-500">
                            Add a schema to reuse it during conversion.
                        </p>
                    </div>
                ) : null}

                {schemas.length > 0 && (
                    <div className="mt-6 grid gap-4">
                        {schemas.map((schema) => (
                            <article
                                key={schema.id}
                                className="rounded-xl border border-gray-200 bg-gray-50 p-5"
                            >
                                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <h3 className="text-base font-semibold text-gray-900">
                                                {schema.name}
                                            </h3>
                                            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-gray-600">
                                                v{schema.version}
                                            </span>
                                        </div>

                                        {schema.description && (
                                            <p className="mt-2 text-sm text-gray-600">
                                                {schema.description}
                                            </p>
                                        )}

                                        <div className="mt-3 flex flex-wrap gap-2">
                                            {schema.definition.columns.map((column) => (
                                                <span
                                                    key={`${schema.id}-${column.name}`}
                                                    className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700"
                                                >
                                                    {column.name}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => {
                                            void deleteSchema(schema.id)
                                        }}
                                        disabled={deletingSchemaId === schema.id}
                                        className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {deletingSchemaId === schema.id ? 'Deleting...' : 'Delete'}
                                    </button>
                                </div>
                            </article>
                        ))}
                    </div>
                )}
            </section>

            {isModalOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="add-schema-title"
                    onClick={handleBackdropClick}
                    onKeyDown={handleBackdropKeyDown}
                    tabIndex={0}
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-6"
                >
                    <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
                        <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-5">
                            <div>
                                <h3
                                    id="add-schema-title"
                                    className="text-xl font-semibold text-gray-900"
                                >
                                    Add Schema
                                </h3>
                                <p className="mt-1 text-sm text-gray-500">
                                    Define the output columns you want to reuse later.
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={closeCreateModal}
                                disabled={isSaving}
                                aria-label="Close schema dialog"
                                className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                Close
                            </button>
                        </div>

                        <form className="space-y-6 px-6 py-6" onSubmit={handleSubmit}>
                            {formError && (
                                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                    {formError}
                                </div>
                            )}

                            <div>
                                <label
                                    htmlFor="schema-name"
                                    className="mb-1 block text-sm font-medium text-gray-700"
                                >
                                    Schema name
                                </label>
                                <input
                                    id="schema-name"
                                    value={draft.name}
                                    onChange={(event) => {
                                        setFormError(null)
                                        setDraft((prev) => ({
                                            ...prev,
                                            name: event.target.value,
                                        }))
                                    }}
                                    disabled={isSaving}
                                    placeholder="Invoice Extraction"
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:bg-gray-100"
                                />
                            </div>

                            <div>
                                <label
                                    htmlFor="schema-description"
                                    className="mb-1 block text-sm font-medium text-gray-700"
                                >
                                    Description
                                </label>
                                <textarea
                                    id="schema-description"
                                    value={draft.description}
                                    onChange={(event) => {
                                        setFormError(null)
                                        setDraft((prev) => ({
                                            ...prev,
                                            description: event.target.value,
                                        }))
                                    }}
                                    disabled={isSaving}
                                    placeholder="Describe what this schema is for."
                                    rows={3}
                                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:bg-gray-100"
                                />
                            </div>

                            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <h4 className="text-sm font-semibold text-gray-900">
                                            Output columns
                                        </h4>
                                        <p className="text-sm text-gray-500">
                                            Each column needs a name and a description.
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={handleAddColumn}
                                        disabled={isSaving}
                                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        Add column
                                    </button>
                                </div>

                                <div className="mt-4 space-y-3">
                                    {draft.columns.map((column, index) => (
                                        <div
                                            key={column.id}
                                            className="rounded-lg border border-gray-200 bg-white p-4"
                                        >
                                            <div className="mb-3 flex items-center justify-between gap-3">
                                                <p className="text-sm font-semibold text-gray-800">
                                                    Column {index + 1}
                                                </p>
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveColumn(column.id)}
                                                    disabled={
                                                        isSaving || draft.columns.length === 1
                                                    }
                                                    className="text-sm font-medium text-red-700 transition hover:text-red-800 disabled:cursor-not-allowed disabled:text-gray-400"
                                                >
                                                    Remove
                                                </button>
                                            </div>

                                            <div className="grid gap-3 md:grid-cols-2">
                                                <div>
                                                    <label
                                                        htmlFor={`schema-column-name-${column.id}`}
                                                        className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500"
                                                    >
                                                        Column name
                                                    </label>
                                                    <input
                                                        id={`schema-column-name-${column.id}`}
                                                        value={column.name}
                                                        onChange={(event) => {
                                                            handleColumnChange(
                                                                column.id,
                                                                'name',
                                                                event.target.value
                                                            )
                                                        }}
                                                        disabled={isSaving}
                                                        placeholder="invoice_number"
                                                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:bg-gray-100"
                                                    />
                                                </div>

                                                <div>
                                                    <label
                                                        htmlFor={`schema-column-description-${column.id}`}
                                                        className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500"
                                                    >
                                                        Column description
                                                    </label>
                                                    <input
                                                        id={`schema-column-description-${column.id}`}
                                                        value={column.description}
                                                        onChange={(event) => {
                                                            handleColumnChange(
                                                                column.id,
                                                                'description',
                                                                event.target.value
                                                            )
                                                        }}
                                                        disabled={isSaving}
                                                        placeholder="Invoice identifier"
                                                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:bg-gray-100"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="flex flex-col gap-3 border-t border-gray-200 pt-4 md:flex-row md:items-center md:justify-end">
                                <button
                                    type="button"
                                    onClick={closeCreateModal}
                                    disabled={isSaving}
                                    className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    Cancel
                                </button>
                                <button
                                    data-testid="schema-save-btn"
                                    type="submit"
                                    disabled={isSaving}
                                    className="rounded-xl bg-red-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {isSaving ? 'Saving...' : 'Save schema'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    )
}
