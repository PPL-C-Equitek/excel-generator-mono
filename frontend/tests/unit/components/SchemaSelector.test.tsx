import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SchemaSelector from '../../../src/components/SchemaSelector'
import type {
    CustomSchemaRecord,
    ICustomSchemaService,
} from '../../../src/lib/ICustomSchemaService'

function createSchemaRecord(overrides: Partial<CustomSchemaRecord> = {}): CustomSchemaRecord {
    return {
        id: 1,
        owner_id: '11111111-1111-1111-1111-111111111111',
        name: 'Invoice Mapping',
        description: 'Maps invoice rows',
        version: 1,
        is_active: true,
        definition: {
            columns: [
                {
                    name: 'invoice_number',
                    description: 'Invoice identifier',
                },
            ],
        },
        prompt_fragment: 'Prompt fragment',
        created_at: '2026-04-01T10:00:00Z',
        updated_at: '2026-04-01T10:00:00Z',
        ...overrides,
    }
}

function createService(overrides: Partial<ICustomSchemaService> = {}): ICustomSchemaService {
    return {
        list: vi.fn().mockResolvedValue([]),
        create: vi.fn(),
        remove: vi.fn(),
        ...overrides,
    }
}

describe('SchemaSelector', () => {
    beforeEach(() => {
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    afterEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    it('stays quiet when there is no access token', () => {
        render(
            <SchemaSelector
                service={createService()}
                accessTokenResolver={() => null}
            />
        )

        expect(screen.queryByTestId('schema-select')).not.toBeInTheDocument()
        expect(screen.queryByText(/sign in to choose from your saved schemas/i)).not.toBeInTheDocument()
    })

    it('renders saved schemas and defaults to no schema', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({ id: 1, name: 'Invoice Mapping', is_active: false }),
                createSchemaRecord({
                    id: 2,
                    name: 'Receipt Mapping',
                    is_active: true,
                    definition: {
                        columns: [
                            { name: 'receipt_number', description: 'Receipt identifier' },
                        ],
                    },
                }),
            ]),
        })

        render(
            <SchemaSelector
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await waitFor(() => {
            expect(service.list).toHaveBeenCalledWith('access-token')
        })

        const select = screen.getByTestId('schema-select')
        expect(select).toHaveValue('none')
        expect(screen.queryByRole('heading', { name: 'Receipt Mapping' })).not.toBeInTheDocument()
    })

    it('updates the selected schema preview when the user chooses one', async () => {
        const user = userEvent.setup()
        const onSchemaChange = vi.fn()
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({
                    id: 1,
                    name: 'Invoice Mapping',
                    definition: {
                        columns: [
                            { name: 'invoice_number', description: 'Invoice identifier' },
                        ],
                    },
                }),
                createSchemaRecord({
                    id: 2,
                    name: 'Receipt Mapping',
                    definition: {
                        columns: [
                            { name: 'receipt_number', description: 'Receipt identifier' },
                        ],
                    },
                }),
            ]),
        })

        render(
            <SchemaSelector
                service={service}
                accessTokenResolver={() => 'access-token'}
                onSchemaChange={onSchemaChange}
            />
        )

        const select = await screen.findByTestId('schema-select')
        await user.selectOptions(select, '2')

        await waitFor(() => {
            expect(
                screen.getByRole('heading', { name: 'Receipt Mapping' })
            ).toBeInTheDocument()
        })

        expect(screen.getByText('receipt_number')).toBeInTheDocument()
        expect(screen.queryByText(/^Active$/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/^Inactive$/i)).not.toBeInTheDocument()
        expect(onSchemaChange).toHaveBeenLastCalledWith(
            expect.objectContaining({ id: 2, name: 'Receipt Mapping' })
        )
    })
})
