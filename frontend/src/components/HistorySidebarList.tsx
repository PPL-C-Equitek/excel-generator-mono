'use client'

import Link from 'next/link'
import { useMemo, useState, type ClipboardEvent, type FormEvent } from 'react'
import type { HistoryItem } from '@/services/history'
import { getSessionResume } from '@/services/sessions'

const HISTORY_FILE_NAME_MAX_LENGTH = 120
const HISTORY_TITLE_EMPTY_ERROR_MESSAGE = 'Title cannot be empty.'
const HISTORY_TITLE_MAX_LENGTH_ERROR_MESSAGE = 'Max 120 Character'

function getDisplayName(customName: string, originalName: string): string {
    return customName.trim() || originalName
}

function getHistoryGroupLabel(value: string): string {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
        return 'Older'
    }

    const now = new Date()
    const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
    const target = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())
    const diffDays = Math.floor((today - target) / (24 * 60 * 60 * 1000))

    if (diffDays <= 0) {
        return 'Today'
    }

    if (diffDays === 1) {
        return 'Yesterday'
    }

    if (diffDays <= 7) {
        return 'Last 7 days'
    }

    if (diffDays <= 30) {
        return 'Last 30 days'
    }

    return 'Older'
}

interface HistorySidebarListProps {
    readonly selectedHistoryId?: string | null
    readonly items: HistoryItem[]
    readonly isLoading: boolean
    readonly loadError: string | null
    readonly renamingHistoryId: string | null
    readonly deletingHistoryId: string | null
    readonly reloadHistory: () => Promise<void>
    readonly renameHistory: (historyId: string, customName: string) => Promise<boolean>
    readonly deleteHistory: (historyId: string) => Promise<boolean>
}

interface HistoryGroup {
    readonly label: string
    readonly items: HistoryItem[]
}

interface HistorySidebarItemRowProps {
    readonly item: HistoryItem
    readonly selectedHistoryId: string | null
    readonly isMenuOpen: boolean
    readonly onToggleMenu: (itemId: string) => void
    readonly onRename: (item: HistoryItem) => void
    readonly onDelete: (item: HistoryItem) => void
}

interface HistorySidebarGroupSectionProps {
    readonly group: HistoryGroup
    readonly selectedHistoryId: string | null
    readonly openMenuHistoryId: string | null
    readonly onToggleMenu: (itemId: string) => void
    readonly onRename: (item: HistoryItem) => void
    readonly onDelete: (item: HistoryItem) => void
}

interface HistorySidebarContentProps {
    readonly isLoading: boolean
    readonly loadError: string | null
    readonly shouldShowLoadError: boolean
    readonly shouldShowEmptyState: boolean
    readonly shouldShowNoMatches: boolean
    readonly shouldShowGroups: boolean
    readonly groupedItems: HistoryGroup[]
    readonly selectedHistoryId: string | null
    readonly openMenuHistoryId: string | null
    readonly onToggleMenu: (itemId: string) => void
    readonly onRename: (item: HistoryItem) => void
    readonly onDelete: (item: HistoryItem) => void
    readonly onRetry: () => void
}

interface RenameHistoryDialogProps {
    readonly target: HistoryItem | null
    readonly value: string
    readonly validationError: string | null
    readonly isPending: boolean
    readonly onChangeValue: (value: string) => void
    readonly onMaxLengthBlocked: () => void
    readonly onCancel: () => void
    readonly onSubmit: (target: HistoryItem) => void
}

interface DeleteHistoryDialogProps {
    readonly target: HistoryItem | null
    readonly isPending: boolean
    readonly onCancel: () => void
    readonly onConfirm: (target: HistoryItem) => void
}

function HistorySidebarItemRow({
    item,
    selectedHistoryId,
    isMenuOpen,
    onToggleMenu,
    onRename,
    onDelete,
}: HistorySidebarItemRowProps) {
    const historyName = getDisplayName(item.custom_name, item.original_name)
    const isSelected = selectedHistoryId === item.id
    const historyHref = item.session_id
        ? {
            pathname: '/history',
            query: {
                historyId: item.id,
                sessionId: item.session_id,
            },
        }
        : `/history?historyId=${item.id}`
    const sessionId = item.session_id ?? null

    return (
        <div
            key={item.id}
            className={`group relative rounded-xl transition ${
                isSelected
                    ? 'border border-white bg-white text-red-700 shadow-md'
                    : 'border border-transparent bg-transparent text-white hover:border-white/35 hover:bg-white/16'
            }`}
        >
            <div className="flex items-start gap-1 px-2 py-1.5">
                <Link
                    href={historyHref}
                    className="min-w-0 flex-1 rounded-md px-2 py-1 text-left transition focus:outline-none"
                    title={historyName}
                    onClick={() => {
                        if (!sessionId) {
                            return
                        }

                        void Promise.resolve(getSessionResume(sessionId)).catch(() => {
                            // SessionDetail handles final fallback state.
                        })
                    }}
                >
                    <p className="truncate text-sm font-semibold">{historyName}</p>
                </Link>

                <button
                    type="button"
                    aria-label={`Actions for ${historyName}`}
                    className={`mt-0.5 rounded-md px-1.5 py-1 text-sm font-bold leading-none transition focus:outline-none focus:ring-2 focus:ring-white/40 ${
                        isSelected
                            ? 'text-red-700 hover:bg-red-100'
                            : 'text-white/70 hover:bg-white/20 hover:text-white group-hover:text-white/90'
                    }`}
                    onClick={() => {
                        onToggleMenu(item.id)
                    }}
                >
                    ...
                </button>
            </div>

            {isMenuOpen ? (
                <div className="absolute right-2 top-10 z-20 w-36 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                    <button
                        type="button"
                        className="block w-full rounded-md px-3 py-2 text-left text-xs font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300"
                        onClick={() => {
                            onRename(item)
                        }}
                    >
                        Rename
                    </button>
                    <button
                        type="button"
                        className="mt-1 block w-full rounded-md px-3 py-2 text-left text-xs font-semibold text-red-700 transition hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-200"
                        onClick={() => {
                            onDelete(item)
                        }}
                    >
                        Delete
                    </button>
                </div>
            ) : null}
        </div>
    )
}

function HistorySidebarGroupSection({
    group,
    selectedHistoryId,
    openMenuHistoryId,
    onToggleMenu,
    onRename,
    onDelete,
}: HistorySidebarGroupSectionProps) {
    return (
        <section key={group.label} className="mb-2">
            <h2 className="mb-1 px-4 text-[10px] font-semibold uppercase tracking-[0.12em] text-red-100">
                {group.label}
            </h2>
            <div className="space-y-1">
                {group.items.map((item) => (
                    <HistorySidebarItemRow
                        key={item.id}
                        item={item}
                        selectedHistoryId={selectedHistoryId}
                        isMenuOpen={openMenuHistoryId === item.id}
                        onToggleMenu={onToggleMenu}
                        onRename={onRename}
                        onDelete={onDelete}
                    />
                ))}
            </div>
        </section>
    )
}

function HistorySidebarContent({
    isLoading,
    loadError,
    shouldShowLoadError,
    shouldShowEmptyState,
    shouldShowNoMatches,
    shouldShowGroups,
    groupedItems,
    selectedHistoryId,
    openMenuHistoryId,
    onToggleMenu,
    onRename,
    onDelete,
    onRetry,
}: HistorySidebarContentProps) {
    return (
        <div className="mt-3 min-h-0 flex-1 overflow-y-auto pb-2">
            {isLoading ? <p className="px-4 text-sm text-white/75">Loading history...</p> : null}

            {shouldShowLoadError ? (
                <div className="mx-1 rounded-xl border border-red-200/50 bg-red-50/90 p-3 text-xs text-red-700">
                    <p>{loadError}</p>
                    <button
                        type="button"
                        className="mt-2 rounded-md bg-red-700 px-2 py-1 text-[11px] font-semibold text-white hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300"
                        onClick={onRetry}
                    >
                        Retry
                    </button>
                </div>
            ) : null}

            {shouldShowEmptyState ? (
                <p className="px-4 text-sm text-white/75">No history yet</p>
            ) : null}

            {shouldShowNoMatches ? (
                <p className="px-4 text-sm text-white/75">No matches.</p>
            ) : null}

            {shouldShowGroups
                ? groupedItems.map((group) => (
                    <HistorySidebarGroupSection
                        key={group.label}
                        group={group}
                        selectedHistoryId={selectedHistoryId}
                        openMenuHistoryId={openMenuHistoryId}
                        onToggleMenu={onToggleMenu}
                        onRename={onRename}
                        onDelete={onDelete}
                    />
                ))
                : null}
        </div>
    )
}

function RenameHistoryDialog({
    target,
    value,
    validationError,
    isPending,
    onChangeValue,
    onMaxLengthBlocked,
    onCancel,
    onSubmit,
}: RenameHistoryDialogProps) {
    if (!target) {
        return null
    }

    const handleBeforeInput = (event: FormEvent<HTMLInputElement>) => {
        const nativeEvent = event.nativeEvent as InputEvent
        const typedText = nativeEvent.data
        if (!typedText) {
            return
        }

        const targetInput = event.currentTarget
        const selectionStart = targetInput.selectionStart ?? targetInput.value.length
        const selectionEnd = targetInput.selectionEnd ?? selectionStart
        const selectedLength = Math.max(0, selectionEnd - selectionStart)
        const nextLength = targetInput.value.length - selectedLength + typedText.length

        if (nextLength > HISTORY_FILE_NAME_MAX_LENGTH) {
            event.preventDefault()
            onMaxLengthBlocked()
        }
    }

    const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
        const pastedText = event.clipboardData.getData('text')
        if (!pastedText) {
            return
        }

        const targetInput = event.currentTarget
        const selectionStart = targetInput.selectionStart ?? targetInput.value.length
        const selectionEnd = targetInput.selectionEnd ?? selectionStart
        const selectedLength = Math.max(0, selectionEnd - selectionStart)
        const nextLength = targetInput.value.length - selectedLength + pastedText.length

        if (nextLength > HISTORY_FILE_NAME_MAX_LENGTH) {
            event.preventDefault()
            onMaxLengthBlocked()
        }
    }

    return (
        <>
            <div className="fixed inset-0 z-40 bg-slate-900/70" />
            <dialog
                open
                className="fixed inset-0 z-50 m-auto w-full max-w-sm rounded-2xl border border-red-100 bg-white p-5 shadow-2xl shadow-slate-900/15"
            >
                <h3 className="text-base font-bold text-slate-900">Rename History</h3>
                <p className="mt-1 text-xs text-slate-600">Update the display name for this history item.</p>
                <label className="mt-4 block">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                        File Name
                    </span>
                    <input
                        type="text"
                        value={value}
                        onChange={(event) => {
                            onChangeValue(event.target.value)
                        }}
                        onBeforeInput={handleBeforeInput}
                        onPaste={handlePaste}
                        className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-red-300 focus:ring-2 focus:ring-red-100"
                        maxLength={HISTORY_FILE_NAME_MAX_LENGTH}
                        disabled={isPending}
                    />
                </label>
                {validationError ? (
                    <p className="mt-2 text-xs text-red-700">{validationError}</p>
                ) : null}
                <div className="mt-4 flex justify-end gap-2">
                    <button
                        type="button"
                        className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300"
                        onClick={onCancel}
                        disabled={isPending}
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        className="rounded-lg bg-red-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => {
                            onSubmit(target)
                        }}
                        disabled={isPending}
                    >
                        {isPending ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </dialog>
        </>
    )
}

function DeleteHistoryDialog({
    target,
    isPending,
    onCancel,
    onConfirm,
}: DeleteHistoryDialogProps) {
    if (!target) {
        return null
    }

    return (
        <>
            <div className="fixed inset-0 z-40 bg-slate-900/70" />
            <dialog
                open
                className="fixed inset-0 z-50 m-auto w-full max-w-sm rounded-2xl border border-red-100 bg-white p-5 shadow-2xl shadow-slate-900/15"
            >
                <h3 className="text-base font-bold text-slate-900">Delete History</h3>
                <p className="mt-2 text-sm text-slate-600">
                    Remove this history item from the list?
                </p>
                <div className="mt-4 flex justify-end gap-2">
                    <button
                        type="button"
                        className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-300"
                        onClick={onCancel}
                        disabled={isPending}
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        className="rounded-lg bg-red-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => {
                            onConfirm(target)
                        }}
                        disabled={isPending}
                    >
                        {isPending ? 'Deleting...' : 'Delete'}
                    </button>
                </div>
            </dialog>
        </>
    )
}

export default function HistorySidebarList({
    selectedHistoryId = null,
    items,
    isLoading,
    loadError,
    renamingHistoryId,
    deletingHistoryId,
    reloadHistory,
    renameHistory,
    deleteHistory,
}: HistorySidebarListProps) {
    const [searchQuery, setSearchQuery] = useState('')
    const [openMenuHistoryId, setOpenMenuHistoryId] = useState<string | null>(null)
    const [renameTarget, setRenameTarget] = useState<HistoryItem | null>(null)
    const [renameValue, setRenameValue] = useState('')
    const [renameValidationError, setRenameValidationError] = useState<string | null>(null)
    const [deleteTarget, setDeleteTarget] = useState<HistoryItem | null>(null)
    const filteredItems = useMemo(() => {
        const normalizedQuery = searchQuery.trim().toLowerCase()
        if (!normalizedQuery) {
            return items
        }

        return items.filter((item) =>
            getDisplayName(item.custom_name, item.original_name)
                .toLowerCase()
                .includes(normalizedQuery)
        )
    }, [items, searchQuery])

    const groupedItems = useMemo<HistoryGroup[]>(() => {
        const groups = new Map<string, HistoryItem[]>()

        filteredItems.forEach((item) => {
            const label = getHistoryGroupLabel(item.created_at)
            const existing = groups.get(label)

            if (existing) {
                existing.push(item)
                return
            }

            groups.set(label, [item])
        })

        const groupOrder = ['Today', 'Yesterday', 'Last 7 days', 'Last 30 days', 'Older']

        return groupOrder
            .map((label) => ({
                label,
                items: groups.get(label) ?? [],
            }))
            .filter((group) => group.items.length > 0)
    }, [filteredItems])

    const hasItems = items.length > 0
    const isRenaming = renameTarget !== null && renamingHistoryId === renameTarget.id
    const isDeleting = deleteTarget !== null && deletingHistoryId === deleteTarget.id
    const shouldShowLoadError = !isLoading && Boolean(loadError)
    const shouldShowEmptyState = !isLoading && !loadError && !hasItems
    const shouldShowNoMatches = !isLoading && !loadError && hasItems && !filteredItems.length
    const shouldShowGroups = !isLoading && !loadError

    const toggleMenu = (itemId: string) => {
        setOpenMenuHistoryId((current) => (current === itemId ? null : itemId))
    }

    const openRenameDialog = (item: HistoryItem) => {
        setRenameTarget(item)
        setRenameValue(getDisplayName(item.custom_name, item.original_name))
        setRenameValidationError(null)
        setOpenMenuHistoryId(null)
    }

    const openDeleteDialog = (item: HistoryItem) => {
        setDeleteTarget(item)
        setOpenMenuHistoryId(null)
    }

    const handleRenameSubmit = async (target: HistoryItem) => {
        const normalizedRenameValue = renameValue.trim()
        if (!normalizedRenameValue) {
            setRenameValidationError(HISTORY_TITLE_EMPTY_ERROR_MESSAGE)
            return
        }

        if (normalizedRenameValue.length > HISTORY_FILE_NAME_MAX_LENGTH) {
            setRenameValidationError(HISTORY_TITLE_MAX_LENGTH_ERROR_MESSAGE)
            return
        }

        setRenameValidationError(null)
        const didRename = await renameHistory(target.id, normalizedRenameValue)
        if (didRename) {
            setRenameTarget(null)
            setRenameValue('')
            setRenameValidationError(null)
        }
    }

    const handleDeleteConfirm = async (target: HistoryItem) => {
        const didDelete = await deleteHistory(target.id)
        if (didDelete) {
            setDeleteTarget(null)
        }
    }

    const handleRetry = () => {
        void reloadHistory()
    }

    const closeRenameDialog = () => {
        setRenameTarget(null)
        setRenameValue('')
        setRenameValidationError(null)
    }

    const handleRenameChangeValue = (value: string) => {
        setRenameValue(value)
        if (renameValidationError) {
            setRenameValidationError(null)
        }
    }

    const handleRenameMaxLengthBlocked = () => {
        setRenameValidationError(HISTORY_TITLE_MAX_LENGTH_ERROR_MESSAGE)
    }

    const closeDeleteDialog = () => {
        setDeleteTarget(null)
    }

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <div className="px-4">
                <p className="text-sm font-semibold uppercase tracking-[0.16em] text-red-100">
                    History List
                </p>
            </div>

            <div className="mt-2 px-2">
                <label className="relative block">
                    <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-white/80">
                        <svg
                            viewBox="0 0 20 20"
                            fill="none"
                            className="h-4 w-4"
                            aria-hidden="true"
                        >
                            <circle cx="9" cy="9" r="5.5" stroke="currentColor" strokeWidth="1.5" />
                            <path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                    </span>
                    <input
                        type="search"
                        aria-label="Search history"
                        value={searchQuery}
                        onChange={(event) => {
                            setSearchQuery(event.target.value)
                        }}
                        placeholder="Search history"
                        className="w-full rounded-xl border border-white/40 bg-white/20 py-2.5 pl-9 pr-3 text-sm text-white outline-none placeholder:text-white/75 focus:border-white focus:ring-2 focus:ring-white/35"
                    />
                </label>
            </div>

            <HistorySidebarContent
                isLoading={isLoading}
                loadError={loadError}
                shouldShowLoadError={shouldShowLoadError}
                shouldShowEmptyState={shouldShowEmptyState}
                shouldShowNoMatches={shouldShowNoMatches}
                shouldShowGroups={shouldShowGroups}
                groupedItems={groupedItems}
                selectedHistoryId={selectedHistoryId}
                openMenuHistoryId={openMenuHistoryId}
                onToggleMenu={toggleMenu}
                onRename={openRenameDialog}
                onDelete={openDeleteDialog}
                onRetry={handleRetry}
            />

            <RenameHistoryDialog
                target={renameTarget}
                value={renameValue}
                validationError={renameValidationError}
                isPending={isRenaming}
                onChangeValue={handleRenameChangeValue}
                onMaxLengthBlocked={handleRenameMaxLengthBlocked}
                onCancel={closeRenameDialog}
                onSubmit={(target) => {
                    void handleRenameSubmit(target)
                }}
            />

            <DeleteHistoryDialog
                target={deleteTarget}
                isPending={isDeleting}
                onCancel={closeDeleteDialog}
                onConfirm={(target) => {
                    void handleDeleteConfirm(target)
                }}
            />
        </div>
    )
}
