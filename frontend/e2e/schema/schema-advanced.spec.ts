import { expect, test } from '@playwright/test'

type SeedSchemaRecord = {
  id: string
  owner_id: string
  name: string
  description: string
  is_active: boolean
  definition: {
    columns: { name: string; description: string }[]
  }
  prompt_fragment: string
  created_at: string
  updated_at: string
}

function createSchemaRecord(overrides: Partial<SeedSchemaRecord> = {}): SeedSchemaRecord {
  return {
    id: `00000000-0000-0000-0000-000000000001`,
    owner_id: `11111111-1111-1111-1111-111111111111`,
    name: 'Base Schema',
    description: 'Base schema description',
    is_active: false,
    definition: {
      columns: [
        {
          name: 'unit',
          description: 'Unit name',
        },
      ],
    },
    prompt_fragment: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function createFiveSchemas(): SeedSchemaRecord[] {
  return Array.from({ length: 5 }, (_item, index) => {
    return createSchemaRecord({
      id: `00000000-0000-0000-0000-${String(index + 1).padStart(12, '0')}`,
      name: `Schema ${index + 1}`,
      description: `Schema ${index + 1} description`,
    })
  })
}

test('trims schema and column fields before posting payload', async ({ page }) => {
  let createPayload: Record<string, unknown> | null = null

  await page.route('**/schemas/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([createSchemaRecord()]),
      })
      return
    }

    const rawBody = route.request().postData()
    createPayload = rawBody ? JSON.parse(rawBody) : null

    const payload = (createPayload ?? {}) as {
      name?: string
      description?: string
      definition?: { columns?: { name: string; description: string }[] }
      is_active?: boolean
    }

    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        id: `22222222-2222-2222-2222-222222222222`,
        owner_id: `33333333-3333-3333-3333-333333333333`,
        name: payload.name ?? 'Truncated Schema',
        description: payload.description ?? '',
        is_active: payload.is_active ?? false,
        definition: payload.definition ?? { columns: [] },
        prompt_fragment: '',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }),
    })
  })

  await page.goto('/schema')

  await expect(page.getByRole('heading', { name: 'Manage Your Custom Schemas' })).toBeVisible()
  await page.getByTestId('add-schema-btn').click()

  const createDialog = page.getByRole('dialog', { name: /add schema/i })
  await expect(createDialog).toBeVisible()

  await page.locator('#schema-name').fill('   Sales Snapshot ')
  await page.locator('#schema-description').fill('   Tracks monthly sales data. ')
  await page.locator('#schema-column-name-1').fill('   unit_name   ')
  await page.locator('#schema-column-description-1').fill('   Main unit value ')
  const createRequest = page.waitForResponse((response) => {
    return response.url().includes('/schemas/') && response.request().method() === 'POST'
  })
  await page.getByTestId('schema-save-btn').click()
  await createRequest

  expect(createPayload).toMatchObject({
    name: 'Sales Snapshot',
    description: 'Tracks monthly sales data.',
    is_active: false,
    definition: {
      columns: [
        {
          name: 'unit_name',
          description: 'Main unit value',
        },
      ],
    },
  })

  await expect(createDialog).not.toBeVisible()
  await expect(page.getByTestId('schema-count')).toHaveText('2/5 saved')
  await expect(page.getByText('Sales Snapshot')).toBeVisible()
})

test('shows backend duplicate-name message and keeps the modal open', async ({ page }) => {
  let createPayload: Record<string, unknown> | null = null

  await page.route('**/schemas/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([createSchemaRecord({ name: 'E2E Baseline Schema' })]),
      })
      return
    }

    const rawBody = route.request().postData()
    createPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        message: 'You already have a custom schema with this name.',
      }),
    })
  })

  await page.goto('/schema')
  await page.getByTestId('add-schema-btn').click()
  const createDialog = page.getByRole('dialog', { name: /add schema/i })

  await page.locator('#schema-name').fill('   E2E Baseline Schema   ')
  await page.locator('#schema-column-name-1').fill('  unit_name ')
  await page.locator('#schema-column-description-1').fill('  Unit value ')
  const duplicateRequest = page.waitForResponse((response) => {
    return response.url().includes('/schemas/') && response.request().method() === 'POST'
  })
  await page.getByTestId('schema-save-btn').click()
  await duplicateRequest

  await expect(
    createDialog.getByText('You already have a custom schema with this name.')
  ).toBeVisible()
  await expect(page.getByTestId('schema-error')).toHaveCount(0)
  await expect(createDialog).toBeVisible()
  expect(createPayload).toMatchObject({ name: 'E2E Baseline Schema' })
})

test('disables add action when schema limit is reached', async ({ page }) => {
  await page.route('**/schemas/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(createFiveSchemas()),
      })
      return
    }

    await route.fulfill({
      status: 429,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Too many requests' }),
    })
  })

  await page.goto('/schema')

  await expect(page.getByTestId('schema-count')).toHaveText('5/5 saved')
  await expect(page.getByTestId('add-schema-btn')).toBeDisabled()
  await expect(page.getByTestId('schema-error')).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: /add schema/i })).not.toBeVisible()
})

test('trims column name and whitespace-only column description on blur', async ({ page }) => {
  await page.route('**/schemas/', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
      return
    }

    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/schema')
  await page.getByTestId('add-schema-btn').click()

  const columnNameInput = page.locator('#schema-column-name-1')
  await columnNameInput.fill('   unit_name   ')
  await columnNameInput.blur()
  await expect(columnNameInput).toHaveValue('unit_name')

  const columnDescriptionInput = page.locator('#schema-column-description-1')
  await columnDescriptionInput.fill('      ')
  await columnDescriptionInput.blur()
  await expect(columnDescriptionInput).toHaveValue('')
})

test('keeps edit modal open when schema update fails', async ({ page }) => {
  let updatePayload: Record<string, unknown> | null = null

  await page.route('**/schemas/**', async (route) => {
    const method = route.request().method()

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([createSchemaRecord({ name: 'Baseline Schema' })]),
      })
      return
    }

    if (method === 'PATCH') {
      const rawBody = route.request().postData()
      updatePayload = rawBody ? JSON.parse(rawBody) : null
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Unable to update schema at the moment.' }),
      })
      return
    }

    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/schema')

  const schemaCard = page
    .locator('article')
    .filter({ has: page.getByRole('heading', { name: 'Baseline Schema' }) })
    .first()

  await schemaCard.getByRole('button', { name: 'Edit' }).click()
  const editDialog = page.getByRole('dialog', { name: /edit schema/i })
  await expect(editDialog).toBeVisible()

  await page.locator('#schema-name').fill('Updated Schema Name')
  const patchRequest = page.waitForResponse((response) => {
    return (
      response.request().method() === 'PATCH' &&
      response.url().includes('/schemas/')
    )
  })
  await page.getByTestId('schema-save-btn').click()
  await patchRequest

  await expect(editDialog).toBeVisible()
  await expect(editDialog.getByText('Unable to update schema at the moment.')).toBeVisible()
  await expect(page.getByTestId('schema-error')).toHaveText('Unable to update schema at the moment.')
  expect(updatePayload).toMatchObject({ name: 'Updated Schema Name' })
})

test('keeps delete dialog open when schema delete fails', async ({ page }) => {
  await page.route('**/schemas/**', async (route) => {
    const method = route.request().method()

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([createSchemaRecord({ name: 'Delete Target Schema' })]),
      })
      return
    }

    if (method === 'DELETE') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Failed to delete custom schema.' }),
      })
      return
    }

    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/schema')

  const schemaCard = page
    .locator('article')
    .filter({ has: page.getByRole('heading', { name: 'Delete Target Schema' }) })
    .first()

  await schemaCard.getByRole('button', { name: 'Delete' }).click()
  const deleteDialog = page.getByRole('dialog')
  await expect(deleteDialog).toBeVisible()

  const deleteRequest = page.waitForResponse((response) => {
    return (
      response.request().method() === 'DELETE' &&
      response.url().includes('/schemas/')
    )
  })
  await deleteDialog.getByRole('button', { name: 'Delete schema' }).click()
  await deleteRequest

  await expect(deleteDialog).toBeVisible()
  await expect(page.getByTestId('schema-error')).toHaveText('Failed to delete custom schema.')
  await expect(page.getByRole('heading', { name: 'Delete Target Schema' })).toBeVisible()
})
