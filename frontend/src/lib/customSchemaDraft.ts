import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    CustomSchemaDefinition,
} from '@/lib/ICustomSchemaService'

export const MAX_CUSTOM_SCHEMAS = 5

export const CUSTOM_SCHEMA_DUPLICATE_NAME_ERROR_MESSAGE =
    'You already have a custom schema with this name.'
export const CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_MESSAGE_PREFIX =
    'A user can only have up to '
const CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_MESSAGE_PATTERN = new RegExp(
    `^${CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_MESSAGE_PREFIX}\\d+ custom schemas\\.$`
)

export function isCustomSchemaLimitExceededErrorMessage(message: string): boolean {
    if (!message) {
        return false
    }

    const normalized = message.trim()
    return CUSTOM_SCHEMA_LIMIT_EXCEEDED_ERROR_MESSAGE_PATTERN.test(normalized)
}

export interface SchemaColumnDraft {
    id: number
    name: string
    description: string
}

export interface CustomSchemaFormDraft {
    name: string
    description: string
    columns: SchemaColumnDraft[]
}

export function createEmptyColumn(id: number): SchemaColumnDraft {
    return {
        id,
        name: '',
        description: '',
    }
}

export function createEmptyDraft(): CustomSchemaFormDraft {
    return {
        name: '',
        description: '',
        columns: [createEmptyColumn(1)],
    }
}

export function buildDraftFromSchema(schema: CustomSchemaRecord): CustomSchemaFormDraft {
    return {
        name: schema.name,
        description: schema.description,
        columns: schema.definition.columns.map((column, index) => ({
            id: index + 1,
            name: column.name,
            description: column.description,
        })),
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

export function getTrimmedDraftColumns(draft: CustomSchemaFormDraft): CustomSchemaFormDraft {
    return {
        ...draft,
        columns: draft.columns.map((column) => ({
            ...column,
            name: column.name.trim(),
        })),
    }
}

export function getNextColumnsAfterRemoval(
    columns: SchemaColumnDraft[],
    columnId: number
): SchemaColumnDraft[] {
    const remainingColumns = columns.filter((column) => column.id !== columnId)
    return remainingColumns.length === 0 ? columns : remainingColumns
}
