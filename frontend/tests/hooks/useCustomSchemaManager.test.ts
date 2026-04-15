import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCustomSchemaManager } from '../../src/hooks/useCustomSchemaManager'
import type { UseCustomSchemasReturn } from '../../src/hooks/useCustomSchemas'

const mockUseCustomSchemas = vi.fn()

vi.mock('@/hooks/useCustomSchemas', () => ({
    useCustomSchemas: (...args: unknown[]) => mockUseCustomSchemas(...args),
}))

function createHookState(
    overrides: Partial<UseCustomSchemasReturn> = {}
): UseCustomSchemasReturn {
    return {
        hasAccessToken: true,
        isLoading: false,
        isSaving: false,
        deletingSchemaId: null,
        schemas: [],
        saveError: null,
        error: null,
        message: null,
        reloadSchemas: vi.fn().mockResolvedValue(undefined),
        createSchema: vi.fn().mockResolvedValue(true),
        updateSchema: vi.fn().mockResolvedValue(true),
        deleteSchema: vi.fn().mockResolvedValue(true),
        clearSaveError: vi.fn(),
        ...overrides,
    }
}

describe('useCustomSchemaManager', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseCustomSchemas.mockReturnValue(createHookState())
    })

    it('trims column name whitespace for the selected column', () => {
        const { result } = renderHook(() => useCustomSchemaManager())

        act(() => {
            result.current.handleColumnChange(1, 'name', '   unit_name   ')
        })
        act(() => {
            result.current.trimDraftColumnName(1)
        })

        expect(result.current.draft.columns[0].name).toBe('unit_name')
    })

    it('trims only the targeted column name and description', () => {
        const { result } = renderHook(() => useCustomSchemaManager())

        act(() => {
            result.current.handleAddColumn()
        })
        act(() => {
            result.current.handleColumnChange(1, 'name', '  first_name  ')
            result.current.handleColumnChange(1, 'description', '  first description  ')
            result.current.handleColumnChange(2, 'name', '  second_name  ')
            result.current.handleColumnChange(2, 'description', '  second description  ')
        })

        act(() => {
            result.current.trimDraftColumnName(1)
            result.current.trimDraftColumnDescription(2)
        })

        expect(result.current.draft.columns[0].name).toBe('first_name')
        expect(result.current.draft.columns[0].description).toBe('  first description  ')
        expect(result.current.draft.columns[1].name).toBe('  second_name  ')
        expect(result.current.draft.columns[1].description).toBe('second description')
    })

    it('clears a form error through clearFormError()', async () => {
        const { result } = renderHook(() => useCustomSchemaManager())

        await act(async () => {
            await result.current.handleSubmit({
                preventDefault: vi.fn(),
            } as never)
        })

        expect(result.current.formError).toBe('Schema name is required.')

        act(() => {
            result.current.clearFormError()
        })

        expect(result.current.formError).toBeNull()
    })
})
