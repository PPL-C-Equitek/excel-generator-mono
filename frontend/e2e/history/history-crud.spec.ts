import { expect, test } from '@playwright/test'
import { e2eSeedHistoryName } from '../../playwright/env'

test('renames and deletes a seeded history item', async ({ page }) => {
    const renamedHistoryName = `E2E History ${Date.now()}`

    await page.goto('/history')

    await expect(page.getByRole('heading', { name: 'History' })).toBeVisible()

    const originalHistoryCard = page
        .locator('section')
        .filter({ has: page.getByRole('heading', { name: e2eSeedHistoryName }) })
        .first()

    await expect(originalHistoryCard).toBeVisible()
    await originalHistoryCard.getByRole('button', { name: 'Edit Name' }).click()
    await page.getByLabel('File Name').fill(renamedHistoryName)
    await page.getByRole('button', { name: 'Save Name' }).click()

    await expect(page.getByRole('heading', { name: renamedHistoryName })).toBeVisible()

    const renamedHistoryCard = page
        .locator('section')
        .filter({ has: page.getByRole('heading', { name: renamedHistoryName }) })
        .first()

    await renamedHistoryCard.getByRole('button', { name: 'Delete' }).click()

    const deleteDialog = page.getByRole('dialog')
    await expect(deleteDialog).toContainText(renamedHistoryName)
    await deleteDialog.getByRole('button', { name: 'Delete History' }).click()

    await expect(page.getByRole('heading', { name: renamedHistoryName })).toHaveCount(0)
})
