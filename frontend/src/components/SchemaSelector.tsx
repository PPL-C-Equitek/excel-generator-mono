'use client'

import { useEffect, useMemo, useState } from 'react'
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

const NO_SCHEMA_VALUE = 'none'

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
    const [selectedSchemaId, setSelectedSchemaId] = useState<string>(NO_SCHEMA_VALUE)
    const [isDropdownOpen, setIsDropdownOpen] = useState(false)

    const selectedSchema =
        selectedSchemaId === NO_SCHEMA_VALUE
            ? null
            : schemas.find((schema) => String(schema.id) === selectedSchemaId) ?? null
    const selectValue = selectedSchema ? selectedSchemaId : NO_SCHEMA_VALUE
    const selectedLabel = selectedSchema?.name ?? 'No schema'
    const options = useMemo(
        () => [
            { id: NO_SCHEMA_VALUE, name: 'No schema', description: 'Continue without schema context.' },
            ...schemas.map((schema) => ({
                id: String(schema.id),
                name: schema.name,
                description: 'Use this saved schema for few-shot context.',
            })),
        ],
        [schemas]
    )

    useEffect(() => {
        onSchemaChange?.(selectedSchema)
    }, [onSchemaChange, selectedSchema])

    const handleSelect = (schemaId: string) => {
        setSelectedSchemaId(schemaId)
        setIsDropdownOpen(false)
    }

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
                    className="inline-flex items-center justify-center rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                        <p className="mb-1 block text-sm font-medium text-gray-700">
                            Which schema do you want to use?
                        </p>
                        <div className="relative">
                            <button
                                type="button"
                                data-testid="schema-select"
                                aria-expanded={isDropdownOpen}
                                aria-controls="schema-options"
                                onClick={() => setIsDropdownOpen((isOpen) => !isOpen)}
                                className="flex w-full items-center justify-between gap-3 rounded-xl border border-gray-300 bg-white px-4 py-3 text-left shadow-sm transition hover:border-red-300 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                <span className="min-w-0">
                                    <span className="block truncate text-sm font-semibold text-gray-900">
                                        {selectedLabel}
                                    </span>
                                    <span className="mt-0.5 block text-xs text-gray-500">
                                        {selectedSchema ? 'Saved schema selected' : 'No schema context selected'}
                                    </span>
                                </span>
                                <span
                                    aria-hidden="true"
                                    data-testid="schema-select-chevron"
                                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-700 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`}
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
                            </button>

                            {isDropdownOpen && (
                                <div
                                    id="schema-options"
                                    data-testid="schema-options"
                                    className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-2xl border border-gray-200 bg-white p-2 shadow-xl"
                                >
                                    {options.map((option) => {
                                        const isSelected = option.id === selectValue
                                        return (
                                            <button
                                                key={option.id}
                                                type="button"
                                                aria-pressed={isSelected}
                                                data-testid={`schema-option-${option.id}`}
                                                onClick={() => handleSelect(option.id)}
                                                className={`flex w-full items-start justify-between gap-3 rounded-xl px-4 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-blue-500 ${isSelected
                                                    ? 'bg-red-50 text-red-700 ring-1 ring-red-100'
                                                    : 'text-gray-700 hover:bg-gray-50'
                                                    }`}
                                            >
                                                <span className="min-w-0">
                                                    <span className="block truncate text-sm font-semibold">
                                                        {option.name}
                                                    </span>
                                                    <span className={`mt-0.5 block text-xs ${isSelected ? 'text-red-600' : 'text-gray-500'}`}>
                                                        {option.description}
                                                    </span>
                                                </span>
                                                {isSelected && (
                                                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-700 text-white">
                                                        <svg
                                                            className="h-3 w-3"
                                                            viewBox="0 0 12 12"
                                                            fill="none"
                                                            xmlns="http://www.w3.org/2000/svg"
                                                            aria-hidden="true"
                                                        >
                                                            <path
                                                                d="M2.5 6.25L4.75 8.5L9.5 3.5"
                                                                stroke="currentColor"
                                                                strokeWidth="1.75"
                                                                strokeLinecap="round"
                                                                strokeLinejoin="round"
                                                            />
                                                        </svg>
                                                    </span>
                                                )}
                                            </button>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    </div>

                </div>
            )}
        </section>
    )
}
