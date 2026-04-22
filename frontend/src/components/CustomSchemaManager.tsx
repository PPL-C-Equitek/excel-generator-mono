'use client'

import type {
    ICustomSchemaService,
} from '@/lib/ICustomSchemaService'
import {
    MAX_CUSTOM_SCHEMAS,
} from '@/lib/customSchemaDraft'
import { useCustomSchemaManager } from '@/hooks/useCustomSchemaManager'

interface CustomSchemaManagerProps {
    readonly service?: ICustomSchemaService
    readonly accessTokenResolver?: () => string | null | Promise<string | null>
}

export default function CustomSchemaManager({
    service,
    accessTokenResolver,
}: CustomSchemaManagerProps) {
    const {
        draft,
        hasAccessToken,
        isLoading,
        isSaving,
        deletingSchemaId,
        schemas,
        message,
        reloadSchemas,
        isModalOpen,
        isDeleteDialogOpen,
        schemaPendingDeletion,
        formError,
        isAddDisabled,
        modalTitle,
        modalDescription,
        saveButtonLabel,
        shouldShowPageError,
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
    } = useCustomSchemaManager({
        service,
        accessTokenResolver,
    })
    const handleAddSchemaClick = isAddDisabled ? undefined : openCreateModal

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
                            onClick={handleAddSchemaClick}
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
                        className="mt-4 flex items-center gap-4 rounded-2xl border border-red-100 bg-red-50/60 px-4 py-4 text-sm text-slate-800 shadow-sm"
                    >
                        <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-red-700 text-white shadow-sm">
                            <svg
                                className="h-4.5 w-4.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth="2.2"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M9 12.75 11.25 15 15 9.75m6 2.25A9 9 0 1 1 3 12a9 9 0 0 1 18 0Z"
                                />
                            </svg>
                        </span>
                        <span className="font-medium leading-relaxed">{message}</span>
                    </div>
                )}

                {shouldShowPageError && (
                    <div
                        data-testid="schema-error"
                        className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                    >
                        {shouldShowPageError}
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
                                        <h3 className="text-base font-semibold text-gray-900">
                                            {schema.name}
                                        </h3>

                                        {schema.description && (
                                            <p className="mt-2 text-sm text-gray-600">
                                                {schema.description}
                                            </p>
                                        )}
                                    </div>

                                    <div className="flex flex-wrap items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => openEditModal(schema)}
                                            disabled={isSaving || deletingSchemaId === schema.id}
                                            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            Edit
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => openDeleteDialog(schema)}
                                            disabled={deletingSchemaId === schema.id}
                                            className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                            {deletingSchemaId === schema.id
                                                ? 'Deleting...'
                                                : 'Delete'}
                                        </button>
                                    </div>
                                </div>
                            </article>
                        ))}
                    </div>
                )}
            </section>

            {isModalOpen && (
                <dialog
                    open
                    aria-labelledby="add-schema-title"
                    className="fixed inset-0 z-50 m-0 flex h-screen w-screen max-h-none max-w-none items-center justify-center border-0 bg-transparent p-6"
                >
                    <button
                        type="button"
                        data-testid="schema-backdrop-btn"
                        aria-label="Dismiss schema dialog"
                        tabIndex={-1}
                        onClick={closeSchemaModal}
                        disabled={isSaving}
                        className="absolute inset-0 bg-black/45 disabled:cursor-not-allowed"
                    />
                    <div className="relative z-10 max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
                        <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-5">
                            <div>
                                <h3
                                    id="add-schema-title"
                                    className="text-xl font-semibold text-gray-900"
                                >
                                    {modalTitle}
                                </h3>
                                <p className="mt-1 text-sm text-gray-500">{modalDescription}</p>
                            </div>
                            <button
                                type="button"
                                onClick={closeSchemaModal}
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
                                    onChange={(event) => setDraftName(event.target.value)}
                                    disabled={isSaving}
                                    placeholder="Custom Output Schema"
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
                                    onChange={(event) => setDraftDescription(event.target.value)}
                                    onBlur={trimDraftDescription}
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
                                                    disabled={isSaving || draft.columns.length === 1}
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
                                                        onBlur={() => trimDraftColumnName(column.id)}
                                                        disabled={isSaving}
                                                        placeholder="field_name"
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
                                                        onBlur={() =>
                                                            trimDraftColumnDescription(column.id)
                                                        }
                                                        disabled={isSaving}
                                                        placeholder="What this field stores"
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
                                    onClick={closeSchemaModal}
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
                                    {saveButtonLabel}
                                </button>
                            </div>
                        </form>
                    </div>
                </dialog>
            )}

            {isDeleteDialogOpen && schemaPendingDeletion && (
                <dialog
                    open
                    aria-labelledby="delete-schema-title"
                    className="fixed inset-0 z-50 m-0 flex h-screen w-screen max-h-none max-w-none items-center justify-center border-0 bg-transparent p-6"
                >
                    <button
                        type="button"
                        data-testid="delete-schema-backdrop-btn"
                        aria-label="Dismiss delete dialog"
                        tabIndex={-1}
                        onClick={closeDeleteDialog}
                        disabled={deletingSchemaId === schemaPendingDeletion.id}
                        className="absolute inset-0 bg-black/45 disabled:cursor-not-allowed"
                    />
                    <div className="relative z-10 w-full max-w-md rounded-2xl bg-white shadow-2xl">
                        <div className="border-b border-gray-200 px-6 py-5">
                            <h3
                                id="delete-schema-title"
                                className="text-xl font-semibold text-gray-900"
                            >
                                Delete schema?
                            </h3>
                            <p className="mt-2 text-sm text-gray-600">
                                {`"${schemaPendingDeletion.name}" will be removed from your saved schemas.`}
                            </p>
                        </div>
                        <div className="flex flex-col gap-3 px-6 py-5 md:flex-row md:justify-end">
                            <button
                                type="button"
                                onClick={closeDeleteDialog}
                                disabled={deletingSchemaId === schemaPendingDeletion.id}
                                className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                Cancel
                            </button>
                            <button
                                data-testid="confirm-delete-schema-btn"
                                type="button"
                                onClick={() => {
                                    void handleConfirmDelete(schemaPendingDeletion)
                                }}
                                disabled={deletingSchemaId === schemaPendingDeletion.id}
                                className="rounded-xl bg-red-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {deletingSchemaId === schemaPendingDeletion.id
                                    ? 'Deleting...'
                                    : 'Delete schema'}
                            </button>
                        </div>
                    </div>
                </dialog>
            )}
        </>
    )
}

export {
    buildCustomSchemaInput,
    getNextColumnsAfterRemoval,
    validateCustomSchemaDraft,
} from '@/lib/customSchemaDraft'
