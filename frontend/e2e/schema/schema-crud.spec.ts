import { expect, test } from '@playwright/test'

test('creates, updates, and deletes a custom schema', async ({ page }) => {
    const schemaName = `Behavioral Schema ${Date.now()}`
    const updatedSchemaName = `${schemaName} Updated`

    await page.goto('/schema')

    await expect(page.getByRole('heading', { name: 'Manage Your Custom Schemas' })).toBeVisible()
    await page.getByTestId('add-schema-btn').click()

    await expect(page.getByRole('heading', { name: 'Add Schema' })).toBeVisible()
    await page.locator('#schema-name').fill(schemaName)
    await page.locator('#schema-description').fill('Created by the Playwright behavioral smoke suite.')
    await page.locator('#schema-column-name-1').fill('unit')
    await page.locator('#schema-column-description-1').fill('Stores the business unit label.')
    await page.getByTestId('schema-save-btn').click()

    await expect(page.getByRole('heading', { name: schemaName })).toBeVisible()

    const createdSchemaCard = page
        .locator('article')
        .filter({ has: page.getByRole('heading', { name: schemaName }) })
        .first()

    await createdSchemaCard.getByRole('button', { name: 'Edit' }).click()
    await page.locator('#schema-name').fill(updatedSchemaName)
    await page.getByTestId('schema-save-btn').click()

    await expect(page.getByRole('heading', { name: updatedSchemaName })).toBeVisible()

    const updatedSchemaCard = page
        .locator('article')
        .filter({ has: page.getByRole('heading', { name: updatedSchemaName }) })
        .first()

    await updatedSchemaCard.getByRole('button', { name: 'Delete' }).click()

    const deleteDialog = page.getByRole('dialog')
    await expect(deleteDialog).toContainText(updatedSchemaName)
    await deleteDialog.getByRole('button', { name: 'Delete schema' }).click()

    await expect(page.getByRole('heading', { name: updatedSchemaName })).toHaveCount(0)
})
