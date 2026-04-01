'use client'

import { useEffect, useState } from 'react'
import { useCustomSchemas } from '@/hooks/useCustomSchemas'
import { getStoredAccessToken } from '@/lib/auth'
import type {
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'

interface SchemaSelectorProps {
    readonly service?: ICustomSchemaService
    readonly accessTokenResolver?: () => string | null
    readonly onSchemaChange?: (schema: CustomSchemaRecord | null) => void
}

export default function SchemaSelector({
    service = customSchemaService,
    accessTokenResolver = getStoredAccessToken,
    onSchemaChange,
}: SchemaSelectorProps) {
    const { hasAccessToken, isLoading, schemas, error } = useCustomSchemas(
        service,
        accessTokenResolver
    )
    const [selectedSchemaId, setSelectedSchemaId] = useState<string>('none')

    useEffect(() => {
        if (schemas.length === 0) {
            setSelectedSchemaId('none')
            onSchemaChange?.(null)
            return
        }

        if (selectedSchemaId === 'none') {
            onSchemaChange?.(null)
            return
        }

        const nextSchema =
            schemas.find((schema) => String(schema.id) === selectedSchemaId) ?? null

        if (!nextSchema) {
            setSelectedSchemaId('none')
            onSchemaChange?.(null)
            return
        }

        onSchemaChange?.(nextSchema)
    }, [onSchemaChange, schemas, selectedSchemaId])

    const selectedSchema =
        selectedSchemaId === 'none'
            ? null
            : schemas.find((schema) => String(schema.id) === selectedSchemaId) ?? null

    return (
        <section className="mt-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900">Choose A Schema</h2>
                    <p className="mt-1 text-sm text-gray-500">
                        Choose a saved schema if you want to guide this conversion. You can
                        continue without one.
                    </p>
                </div>
                <a
                    href="/schema"
                    className="inline-flex items-center justify-center rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100"
                >
                    Open Schema Builder
                </a>
            </div>

            {error && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {hasAccessToken && isLoading && (
                <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
                    Loading available schemas...
                </div>
            )}

            {hasAccessToken && !isLoading && schemas.length === 0 && (
                <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-500">
                    No saved schemas yet. Create one from the Schema page first.
                </div>
            )}

            {hasAccessToken && !isLoading && schemas.length > 0 && (
                <div className="mt-5 space-y-4">
                    <div>
                        <label
                            htmlFor="convert-schema-select"
                            className="mb-1 block text-sm font-medium text-gray-700"
                        >
                            Which schema do you want to use?
                        </label>
                        <select
                            id="convert-schema-select"
                            data-testid="schema-select"
                            value={selectedSchemaId}
                            onChange={(event) => {
                                const nextValue = event.target.value
                                setSelectedSchemaId(nextValue)

                                if (nextValue === 'none') {
                                    onSchemaChange?.(null)
                                    return
                                }

                                const nextSchema =
                                    schemas.find((schema) => String(schema.id) === nextValue) ?? null
                                onSchemaChange?.(nextSchema)
                            }}
                            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200"
                        >
                            <option value="none">No schema</option>
                            {schemas.map((schema) => (
                                <option key={schema.id} value={String(schema.id)}>
                                    {schema.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedSchema && (
                        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
                            <h3 className="text-base font-semibold text-gray-900">
                                {selectedSchema.name}
                            </h3>

                            {selectedSchema.description && (
                                <p className="mt-2 text-sm text-gray-600">
                                    {selectedSchema.description}
                                </p>
                            )}

                            <div className="mt-3 flex flex-wrap gap-2">
                                {selectedSchema.definition.columns.map((column) => (
                                    <span
                                        key={`${selectedSchema.id}-${column.name}`}
                                        className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700"
                                    >
                                        {column.name}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </section>
    )
}
