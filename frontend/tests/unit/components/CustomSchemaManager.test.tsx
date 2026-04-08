import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CustomSchemaManager, {
    buildCustomSchemaInput,
    validateCustomSchemaDraft,
} from '../../../src/components/CustomSchemaManager'
import type {
    CreateCustomSchemaInput,
    CustomSchemaRecord,
    ICustomSchemaService,
} from '../../../src/lib/ICustomSchemaService'

function createSchemaRecord(overrides: Partial<CustomSchemaRecord> = {}): CustomSchemaRecord {
    return {
        id: '00000000-0000-0000-0000-000000000001',
        owner_id: '11111111-1111-1111-1111-111111111111',
        name: 'Invoice Mapping',
        description: 'Maps invoice rows',
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
        update: vi.fn(),
        remove: vi.fn().mockResolvedValue(undefined),
        ...overrides,
    }
}

describe('CustomSchemaManager', () => {
    beforeEach(() => {
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    afterEach(() => {
        vi.clearAllMocks()
        window.localStorage.clear()
        window.sessionStorage.clear()
    })

    it('stays quiet and disables schema actions when no token is available', () => {
        const service = createService()

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => null}
            />
        )

        expect(service.list).not.toHaveBeenCalled()
        expect(screen.getByTestId('add-schema-btn')).toBeDisabled()
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('loads and renders saved schemas for the current user token', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord(),
                createSchemaRecord({
                    id: '00000000-0000-0000-0000-000000000002',
                    name: 'Receipt Mapping',
                    definition: {
                        columns: [
                            { name: 'receipt_number', description: 'Receipt identifier' },
                        ],
                    },
                }),
            ]),
        })

        const accessTokenResolver = vi.fn().mockReturnValue('access-token')

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={accessTokenResolver}
            />
        )

        await waitFor(() => {
            expect(service.list).toHaveBeenCalledWith('access-token')
        })

        expect(screen.getByText('Invoice Mapping')).toBeInTheDocument()
        expect(screen.getByText('Receipt Mapping')).toBeInTheDocument()
        expect(screen.queryByText('invoice_number')).not.toBeInTheDocument()
        expect(screen.queryByText('receipt_number')).not.toBeInTheDocument()
        expect(screen.getByTestId('schema-count')).toHaveTextContent('2/5 saved')
        expect(screen.getByTestId('add-schema-btn')).toBeEnabled()
        expect(screen.queryByText(/^Active$/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/^Inactive$/i)).not.toBeInTheDocument()
    })

    it('creates a schema from the modal and closes it after a successful save', async () => {
        const user = userEvent.setup()
        const createdSchema = createSchemaRecord({
            id: '00000000-0000-0000-0000-000000000007',
            name: 'Order Mapping',
            description: 'Maps order rows',
            definition: {
                columns: [
                    {
                        name: 'order_id',
                        description: 'Order identifier',
                    },
                    {
                        name: 'customer_name',
                        description: 'Customer full name',
                    },
                ],
            },
        })
        const service = createService({
            create: vi.fn().mockResolvedValue(createdSchema),
        })
        const accessTokenResolver = vi.fn().mockReturnValue('access-token')

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={accessTokenResolver}
            />
        )

        await waitFor(() => {
            expect(service.list).toHaveBeenCalledWith('access-token')
        })

        await user.click(screen.getByTestId('add-schema-btn'))

        const dialog = screen.getByRole('dialog', { name: /add schema/i })
        fireEvent.change(within(dialog).getByLabelText(/schema name/i), {
            target: { value: 'Order Mapping' },
        })
        fireEvent.change(within(dialog).getByLabelText(/^description$/i), {
            target: { value: 'Maps order rows' },
        })
        fireEvent.change(within(dialog).getByLabelText(/column name/i), {
            target: { value: 'order_id' },
        })
        fireEvent.change(within(dialog).getByLabelText(/column description/i), {
            target: { value: 'Order identifier' },
        })
        await user.click(within(dialog).getByRole('button', { name: /add column/i }))
        fireEvent.change(within(dialog).getAllByLabelText(/column name/i)[1], {
            target: { value: 'customer_name' },
        })
        fireEvent.change(within(dialog).getAllByLabelText(/column description/i)[1], {
            target: { value: 'Customer full name' },
        })
        await user.click(within(dialog).getByTestId('schema-save-btn'))

        await waitFor(() => {
            expect(service.create).toHaveBeenCalledWith(
                {
                    name: 'Order Mapping',
                    description: 'Maps order rows',
                    is_active: false,
                    definition: {
                        columns: [
                            { name: 'order_id', description: 'Order identifier' },
                            { name: 'customer_name', description: 'Customer full name' },
                        ],
                    },
                },
                'access-token'
            )
        })

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
        })

        expect(screen.getByText('"Order Mapping" saved successfully.')).toBeInTheDocument()
        expect(screen.getByText('Order Mapping')).toBeInTheDocument()
    })

    it('deletes an existing schema from the rendered list', async () => {
        const user = userEvent.setup()
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            remove: vi.fn().mockResolvedValue(undefined),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /delete/i }))
        expect(
            screen.getByRole('dialog', { name: /delete schema/i })
        ).toBeInTheDocument()
        await user.click(screen.getByTestId('confirm-delete-schema-btn'))

        await waitFor(() => {
            expect(service.remove).toHaveBeenCalledWith(
                '00000000-0000-0000-0000-000000000001',
                'access-token'
            )
        })

        expect(screen.queryByText('Invoice Mapping')).not.toBeInTheDocument()
        expect(screen.getByText('"Invoice Mapping" deleted successfully.')).toBeInTheDocument()
    })

    it('opens the modal in edit mode and updates an existing schema', async () => {
        const user = userEvent.setup()
        const updatedSchema = createSchemaRecord({
            name: 'Updated Invoice Mapping',
            description: 'Updated schema description',
            definition: {
                columns: [
                    {
                        name: 'invoice_code',
                        description: 'Updated invoice identifier',
                    },
                ],
            },
        })
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            update: vi.fn().mockResolvedValue(updatedSchema),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /^edit$/i }))

        const dialog = screen.getByRole('dialog', { name: /edit schema/i })
        const nameInput = within(dialog).getByLabelText(/schema name/i)
        const descriptionInput = within(dialog).getByLabelText(/^description$/i)
        const columnNameInput = within(dialog).getByLabelText(/column name/i)
        const columnDescriptionInput = within(dialog).getByLabelText(/column description/i)

        expect(nameInput).toHaveValue('Invoice Mapping')
        expect(descriptionInput).toHaveValue('Maps invoice rows')
        expect(columnNameInput).toHaveValue('invoice_number')
        expect(columnDescriptionInput).toHaveValue('Invoice identifier')

        await user.clear(nameInput)
        await user.type(nameInput, 'Updated Invoice Mapping')
        await user.clear(descriptionInput)
        await user.type(descriptionInput, 'Updated schema description')
        await user.clear(columnNameInput)
        await user.type(columnNameInput, 'invoice_code')
        await user.clear(columnDescriptionInput)
        await user.type(columnDescriptionInput, 'Updated invoice identifier')
        await user.click(within(dialog).getByTestId('schema-save-btn'))

        await waitFor(() => {
            expect(service.update).toHaveBeenCalledWith(
                '00000000-0000-0000-0000-000000000001',
                {
                    name: 'Updated Invoice Mapping',
                    description: 'Updated schema description',
                    is_active: false,
                    definition: {
                        columns: [
                            {
                                name: 'invoice_code',
                                description: 'Updated invoice identifier',
                            },
                        ],
                    },
                },
                'access-token'
            )
        })

        await waitFor(() => {
            expect(
                screen.queryByRole('dialog', { name: /edit schema/i })
            ).not.toBeInTheDocument()
        })

        expect(screen.getByText('Updated Invoice Mapping')).toBeInTheDocument()
        expect(
            screen.getByText('"Updated Invoice Mapping" updated successfully.')
        ).toBeInTheDocument()
    })

    it('shows the per-user limit and disables adding after five schemas', async () => {
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000001', name: 'Schema 1' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000002', name: 'Schema 2' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000003', name: 'Schema 3' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000004', name: 'Schema 4' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000005', name: 'Schema 5' }),
            ]),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Schema 5')

        expect(screen.getByTestId('schema-count')).toHaveTextContent('5/5 saved')
        expect(screen.getByText(/you have reached the 5-schema limit/i)).toBeInTheDocument()
        expect(screen.getByTestId('add-schema-btn')).toBeDisabled()
    })

    it('does not open the create modal when the add action is forced while disabled', async () => {
        const user = userEvent.setup()
        const service = createService({
            list: vi.fn().mockResolvedValue([
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000001', name: 'Schema 1' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000002', name: 'Schema 2' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000003', name: 'Schema 3' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000004', name: 'Schema 4' }),
                createSchemaRecord({ id: '00000000-0000-0000-0000-000000000005', name: 'Schema 5' }),
            ]),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Schema 5')

        const addButton = screen.getByTestId('add-schema-btn')
        addButton.removeAttribute('disabled')
        await user.click(addButton)

        expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
    })

    it('refreshes the list after an initial load error', async () => {
        const service = createService({
            list: vi
                .fn()
                .mockRejectedValueOnce(new Error('Load failed.'))
                .mockResolvedValueOnce([createSchemaRecord({ name: 'Recovered Schema' })]),
        })
        const user = userEvent.setup()

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Load failed.')
        await user.click(screen.getByRole('button', { name: /refresh/i }))

        await waitFor(() => {
            expect(screen.getByText('Recovered Schema')).toBeInTheDocument()
        })

        expect(service.list).toHaveBeenCalledTimes(2)
    })

    it('shows a validation error when the modal form is submitted without a schema name', async () => {
        const user = userEvent.setup()

        render(
            <CustomSchemaManager
                service={createService()}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))
        await user.click(screen.getByTestId('schema-save-btn'))

        expect(screen.getByText('Schema name is required.')).toBeInTheDocument()
    })

    it('closes the modal when the user clicks the backdrop or presses escape', async () => {
        const user = userEvent.setup()

        render(
            <CustomSchemaManager
                service={createService()}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))
        fireEvent.click(screen.getByTestId('schema-backdrop-btn'))

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
        })

        await user.click(screen.getByTestId('add-schema-btn'))
        fireEvent.keyDown(window, { key: 'Escape' })

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
        })
    })

    it('does not switch to edit mode when the edit action is forced while saving', async () => {
        const user = userEvent.setup()
        let resolveCreate: ((value: CustomSchemaRecord) => void) | null = null
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            create: vi.fn().mockImplementation(
                () =>
                    new Promise<CustomSchemaRecord>((resolve) => {
                        resolveCreate = resolve
                    })
            ),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByTestId('add-schema-btn'))

        const dialog = screen.getByRole('dialog', { name: /add schema/i })
        await user.type(within(dialog).getByLabelText(/schema name/i), 'Pending Save')
        await user.type(within(dialog).getByLabelText(/column name/i), 'invoice_number')
        await user.type(
            within(dialog).getByLabelText(/column description/i),
            'Invoice identifier'
        )
        await user.click(within(dialog).getByTestId('schema-save-btn'))

        const editButton = screen.getByRole('button', { name: /^edit$/i })
        editButton.removeAttribute('disabled')
        await user.click(editButton)

        expect(screen.getByRole('dialog', { name: /add schema/i })).toBeInTheDocument()
        expect(screen.queryByRole('dialog', { name: /edit schema/i })).not.toBeInTheDocument()

        resolveCreate?.(
            createSchemaRecord({
                id: '00000000-0000-0000-0000-000000000099',
                name: 'Pending Save',
            })
        )
        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
        })
    })

    it('keeps the modal open when saving fails', async () => {
        const user = userEvent.setup()
        const service = createService({
            create: vi.fn().mockRejectedValue(new Error('Save failed.')),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))

        const dialog = screen.getByRole('dialog', { name: /add schema/i })
        await user.type(within(dialog).getByLabelText(/schema name/i), 'Invoice Mapping')
        await user.type(within(dialog).getByLabelText(/column name/i), 'invoice_number')
        await user.type(
            within(dialog).getByLabelText(/column description/i),
            'Invoice identifier'
        )
        await user.click(within(dialog).getByTestId('schema-save-btn'))

        expect(await screen.findByText('Save failed.')).toBeInTheDocument()
        expect(screen.getByRole('dialog', { name: /add schema/i })).toBeInTheDocument()
    })

    it('requires delete confirmation before removing a schema', async () => {
        const user = userEvent.setup()
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            remove: vi.fn().mockResolvedValue(undefined),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /delete/i }))
        expect(service.remove).not.toHaveBeenCalled()

        await user.click(screen.getByRole('button', { name: /^cancel$/i }))

        expect(
            screen.queryByRole('dialog', { name: /delete schema/i })
        ).not.toBeInTheDocument()
        expect(service.remove).not.toHaveBeenCalled()
    })

    it('closes the delete dialog when the user clicks the backdrop or presses escape', async () => {
        const user = userEvent.setup()
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /delete/i }))
        fireEvent.click(screen.getByTestId('delete-schema-backdrop-btn'))

        await waitFor(() => {
            expect(
                screen.queryByRole('dialog', { name: /delete schema/i })
            ).not.toBeInTheDocument()
        })

        await user.click(screen.getByRole('button', { name: /delete/i }))
        fireEvent.keyDown(window, { key: 'Escape' })

        await waitFor(() => {
            expect(
                screen.queryByRole('dialog', { name: /delete schema/i })
            ).not.toBeInTheDocument()
        })
    })

    it('keeps the delete dialog open while deletion is in progress', async () => {
        const user = userEvent.setup()
        let resolveDelete: (() => void) | null = null
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            remove: vi.fn().mockImplementation(
                () =>
                    new Promise<void>((resolve) => {
                        resolveDelete = resolve
                    })
            ),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /delete/i }))
        await user.click(screen.getByTestId('confirm-delete-schema-btn'))

        expect(screen.getByTestId('confirm-delete-schema-btn')).toHaveTextContent(
            'Deleting...'
        )

        const cancelButton = screen.getByRole('button', { name: /^cancel$/i })
        cancelButton.removeAttribute('disabled')
        fireEvent.click(screen.getByTestId('delete-schema-backdrop-btn'))
        await user.click(cancelButton)
        fireEvent.keyDown(window, { key: 'Escape' })

        expect(screen.getByRole('dialog', { name: /delete schema/i })).toBeInTheDocument()

        resolveDelete?.()
        await waitFor(() => {
            expect(
                screen.queryByRole('dialog', { name: /delete schema/i })
            ).not.toBeInTheDocument()
        })
    })

    it('keeps the delete dialog open when deletion fails', async () => {
        const user = userEvent.setup()
        const service = createService({
            list: vi.fn().mockResolvedValue([createSchemaRecord()]),
            remove: vi.fn().mockRejectedValue(new Error('Delete failed.')),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await screen.findByText('Invoice Mapping')
        await user.click(screen.getByRole('button', { name: /delete/i }))
        await user.click(screen.getByTestId('confirm-delete-schema-btn'))

        expect(await screen.findByText('Delete failed.')).toBeInTheDocument()
        expect(screen.getByRole('dialog', { name: /delete schema/i })).toBeInTheDocument()
    })

    it('keeps a single column row when the forced remove action targets the last remaining column', async () => {
        const user = userEvent.setup()

        render(
            <CustomSchemaManager
                service={createService()}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))

        const removeButton = screen.getByRole('button', { name: /^remove$/i })
        removeButton.removeAttribute('disabled')
        fireEvent.click(removeButton)

        expect(screen.getAllByText(/column 1/i)).toHaveLength(1)
        expect(screen.getAllByLabelText(/column name/i)).toHaveLength(1)
    })

    it('removes an extra column row from the modal form', async () => {
        const user = userEvent.setup()

        render(
            <CustomSchemaManager
                service={createService()}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))
        await user.click(screen.getByRole('button', { name: /add column/i }))
        expect(screen.getAllByLabelText(/column name/i)).toHaveLength(2)

        await user.click(screen.getAllByRole('button', { name: /^remove$/i })[1])

        expect(screen.getAllByLabelText(/column name/i)).toHaveLength(1)
    })

    it('does not close the modal while a save is still in progress', async () => {
        const user = userEvent.setup()
        let resolveCreate: ((value: CustomSchemaRecord) => void) | null = null

        const service = createService({
            create: vi.fn().mockImplementation(
                () =>
                    new Promise<CustomSchemaRecord>((resolve) => {
                        resolveCreate = resolve
                    })
            ),
        })

        render(
            <CustomSchemaManager
                service={service}
                accessTokenResolver={() => 'access-token'}
            />
        )

        await user.click(screen.getByTestId('add-schema-btn'))
        const dialog = screen.getByRole('dialog', { name: /add schema/i })
        await user.type(within(dialog).getByLabelText(/schema name/i), 'Invoice Mapping')
        await user.type(within(dialog).getByLabelText(/column name/i), 'invoice_number')
        await user.type(
            within(dialog).getByLabelText(/column description/i),
            'Invoice identifier'
        )
        await user.click(within(dialog).getByTestId('schema-save-btn'))

        fireEvent.click(screen.getByTestId('schema-backdrop-btn'))
        fireEvent.keyDown(window, { key: 'Escape' })

        expect(screen.getByRole('dialog', { name: /add schema/i })).toBeInTheDocument()

        resolveCreate?.(createSchemaRecord())

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: /add schema/i })).not.toBeInTheDocument()
        })
    })
})

describe('validateCustomSchemaDraft', () => {
    it('requires a schema name', () => {
        expect(
            validateCustomSchemaDraft({
                name: '   ',
                description: '',
                columns: [{ id: 1, name: 'invoice_number', description: 'Invoice identifier' }],
            })
        ).toBe('Schema name is required.')
    })

    it('rejects duplicate column names', () => {
        expect(
            validateCustomSchemaDraft({
                name: 'Invoice Mapping',
                description: '',
                columns: [
                    { id: 1, name: 'invoice_number', description: 'Invoice identifier' },
                    { id: 2, name: 'Invoice_Number', description: 'Duplicate name' },
                ],
            })
        ).toBe('Column names must be unique.')
    })

    it('requires a column name', () => {
        expect(
            validateCustomSchemaDraft({
                name: 'Invoice Mapping',
                description: '',
                columns: [{ id: 1, name: '   ', description: 'Invoice identifier' }],
            })
        ).toBe('Column 1 name is required.')
    })

    it('requires at least one column', () => {
        expect(
            validateCustomSchemaDraft({
                name: 'Invoice Mapping',
                description: '',
                columns: [],
            })
        ).toBe('Add at least one column.')
    })

    it('requires a column description', () => {
        expect(
            validateCustomSchemaDraft({
                name: 'Invoice Mapping',
                description: '',
                columns: [{ id: 1, name: 'invoice_number', description: '   ' }],
            })
        ).toBe('Column 1 description is required.')
    })
})

describe('buildCustomSchemaInput', () => {
    it('trims the form draft before building the payload', () => {
        const result = buildCustomSchemaInput({
            name: '  Invoice Mapping  ',
            description: '  Maps invoices  ',
            columns: [
                {
                    id: 1,
                    name: ' invoice_number ',
                    description: ' Invoice identifier ',
                },
            ],
        })

        expect(result).toEqual<CreateCustomSchemaInput>({
            name: 'Invoice Mapping',
            description: 'Maps invoices',
            is_active: false,
            definition: {
                columns: [
                    {
                        name: 'invoice_number',
                        description: 'Invoice identifier',
                    },
                ],
            },
        })
    })
})
