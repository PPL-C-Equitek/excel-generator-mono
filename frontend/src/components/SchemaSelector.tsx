'use client'

import { useEffect, useState } from 'react'
import { useCustomSchemas } from '@/hooks/useCustomSchemas'
import { getValidAccessToken } from '@/lib/auth'
import type {
    CustomSchemaRecord,
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import { customSchemaService } from '@/services/customSchemas'

interface SchemaSelectorProps {
    readonly service?: ICustomSchemaService
    readonly accessTokenResolver?: () => string | null | Promise<string | null>
    readonly onSchemaChange?: (schema: CustomSchemaRecord | null) => void
    readonly className?: string
}

export default function SchemaSelector({
    service = customSchemaService,
    accessTokenResolver = getValidAccessToken,
    onSchemaChange,
    className = 'mt-8',
}: SchemaSelectorProps) {
    const { hasAccessToken, isLoading, schemas, error } = useCustomSchemas(
        service,
        accessTokenResolver
    )
    const [selectedSchemaId, setSelectedSchemaId] = useState<string>('none')

    const selectedSchema =
        selectedSchemaId === 'none'
            ? null
            : schemas.find((schema) => String(schema.id) === selectedSchemaId) ?? null
    const selectValue = selectedSchema ? selectedSchemaId : 'none'

    useEffect(() => {
        onSchemaChange?.(selectedSchema)
    }, [onSchemaChange, selectedSchema])

    return (
        <section className={`${className} rounded-xl border border-gray-200 bg-white p-6 shadow-sm`}>
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900">Choose A Schema</h2>
                    <p className="mt-1 text-sm text-gray-500">
                        Use a saved schema, or continue without one.
                    </p>
                </div>
                <a
                    href="/schema"
                    className="inline-flex items-center justify-center rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-100"
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
                        <div className="relative">
                            <select
                                id="convert-schema-select"
                                data-testid="schema-select"
                                value={selectValue}
                                onChange={(event) => {
                                    setSelectedSchemaId(event.target.value)
                                    event.currentTarget.blur()
                                }}
                                className="w-full appearance-none rounded-lg border border-gray-300 px-3 py-2 pr-11 text-sm text-gray-900 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200"
                            >
                                <option value="none">No schema</option>
                                {schemas.map((schema) => (
                                    <option key={schema.id} value={String(schema.id)}>
                                        {schema.name}
                                    </option>
                                ))}
                            </select>
                            <span
                                aria-hidden="true"
                                data-testid="schema-select-chevron"
                                className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-gray-500"
                            >
                                <svg
                                    className="h-4 w-4"
                                    viewBox="0 0 20 20"
                                    fill="none"
                                    xmlns="http://www.w3.org/2000/svg"
                                >
                                    <path
                                        d="M5 7.5L10 12.5L15 7.5"
                                        stroke="currentColor"
                                        strokeWidth="1.75"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    />
                                </svg>
                            </span>
                        </div>
                    </div>

                </div>
            )}
        </section>
    )
}
